"""
run_daily.py – Folio Daily Publication Pipeline Runner.

Orchestrates the full end-to-end morning cycle:
1. fetch_all(): Ingests fresh RSS articles across all feeds (and custom feeds).
2. score_new_articles(): Categorizes and summarizes unscored articles via Gemini.
3. cluster_articles(): Groups articles from the last 48 hours about the same story.
4. build_edition(user_id): Generates personalized daily editions for all registered users.

Can be run:
- Directly via CLI on Windows: python run_daily.py
- Programmatically via POST /api/run-daily
- Automatically via Windows Task Scheduler
"""

import sys
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("folio.run_daily")

from db import get_supabase, DEFAULT_USER_ID, get_or_create_user
from fetcher import fetch_all
from scorer import score_new_articles, cluster_articles
from ranker import build_edition
from learner import decay


def run_daily_pipeline() -> Dict[str, Any]:
    """
    Executes the entire daily morning newspaper pipeline:
    1. Fetch fresh RSS articles
    2. Score and summarize new articles
    3. Cluster articles into multi-perspective stories
    4. Build an edition for every registered user
    """
    logger.info("=== Starting Folio Daily Newspaper Run ===")
    start_time = datetime.now(timezone.utc)

    # 1. Fetch
    logger.info("Step 1/4: Fetching latest RSS feeds...")
    try:
        fetch_res = fetch_all()
    except Exception as e:
        logger.error(f"fetch_all failed: {e}")
        fetch_res = {"articles_saved": 0, "failed_feeds": [{"error": str(e)}]}

    # 2. Score
    logger.info("Step 2/4: Scoring new articles with AI summaries and tone...")
    try:
        score_res = score_new_articles()
    except Exception as e:
        logger.error(f"score_new_articles failed: {e}")
        score_res = {"articles_scored": 0, "error": str(e)}

    # 3. Cluster
    logger.info("Step 3/4: Clustering articles by story...")
    try:
        cluster_res = cluster_articles()
    except Exception as e:
        logger.error(f"cluster_articles failed: {e}")
        cluster_res = {"clusters_formed": 0, "error": str(e)}

    # 4. Build editions for all users
    logger.info("Step 4/4: Building personalized daily editions for all users...")
    client = get_supabase()
    users: List[Dict[str, Any]] = []
    try:
        res = client.table("users").select("id").execute()
        users = res.data or []
    except Exception as e:
        logger.error(f"Failed to fetch users: {e}")

    # Ensure at least the default user exists
    if not users:
        get_or_create_user(DEFAULT_USER_ID)
        users = [{"id": DEFAULT_USER_ID}]

    built_editions = []
    for u in users:
        uid = str(u["id"])
        logger.info(f"Building edition for user: {uid}")
        try:
            edition = build_edition(user_id=uid)
            # Apply decay after edition generation
            try:
                decay(uid)
            except Exception as decay_err:
                logger.debug(f"Decay error for {uid}: {decay_err}")

            built_editions.append({
                "user_id": uid,
                "edition_id": edition.get("id"),
                "status": "success",
                "story_count": len(edition.get("sections", []))
            })
        except Exception as ed_err:
            logger.error(f"Failed to build edition for user {uid}: {ed_err}")
            built_editions.append({
                "user_id": uid,
                "status": "failed",
                "error": str(ed_err)
            })

    elapsed_seconds = round((datetime.now(timezone.utc) - start_time).total_seconds(), 2)
    logger.info(
        f"=== Folio Daily Run Completed in {elapsed_seconds}s. "
        f"Editions built: {len(built_editions)} ==="
    )

    return {
        "status": "completed",
        "elapsed_seconds": elapsed_seconds,
        "fetch": fetch_res,
        "score": score_res,
        "cluster": cluster_res,
        "editions_built": len(built_editions),
        "editions": built_editions
    }


if __name__ == "__main__":
    result = run_daily_pipeline()
    print("\nDaily Run Summary:")
    print(f"- Time taken: {result['elapsed_seconds']}s")
    print(f"- Articles saved: {result['fetch'].get('articles_saved', 0)}")
    print(f"- Articles scored: {result['score'].get('articles_scored', 0)}")
    print(f"- Clusters formed: {result['cluster'].get('clusters_formed', 0)}")
    print(f"- Editions generated: {result['editions_built']}")
