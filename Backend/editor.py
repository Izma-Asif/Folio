import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ai import gemini_json
from db import (
    get_or_create_user,
    get_recent_articles,
    save_edition,
    save_editor_note,
    get_latest_edition,
)
from fetcher import ingest_all_sources
from scorer import score_articles_for_user
from ranker import rank_and_curate_edition

logger = logging.getLogger("folio.editor")


def compose_editor_note(
    user_profile: Dict[str, Any],
    curated_edition: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Uses Gemini to generate the personalized morning Editor-in-Chief note,
    connecting the day's top stories into a coherent narrative.
    """
    lead = curated_edition.get("lead") or {}
    focus = curated_edition.get("focus") or []
    all_selected = curated_edition.get("all_articles") or []

    headlines = [a.get("title", "") for a in all_selected[:6] if a.get("title")]
    lead_title = lead.get("title", "Today's Developments")
    user_depth = user_profile.get("depth", "balanced")
    calm_mode = user_profile.get("calm_mode", False)

    prompt = f"""
You are the Editor-in-Chief of Folio, an intelligent, bespoke morning newspaper.
Write your personal morning Editor's Note for the reader.

Reader Preferences:
- Calm Mode: {calm_mode} (If True, keep the tone measured, rational, and de-escalate sensationalism)
- Depth: {user_depth}

Today's Lead Story: {lead_title}
Key Headlines:
- {chr(10).join('- ' + h for h in headlines)}

Write an engaging, thoughtful Editor's Note (around 120-180 words) that connects the threads between these events and sets an insightful, focused tone for the morning.
Return a JSON object with:
{{
  "summary": "A punchy, memorable one-sentence theme or greeting for the day",
  "note": "The full 2-paragraph morning editorial note",
  "parsed": {{
    "primary_theme": "The core macro theme (e.g. The Acceleration of Machine Intelligence)",
    "reading_time_minutes": 5,
    "key_takeaways": [
      "Key takeaway 1",
      "Key takeaway 2"
    ]
  }}
}}
"""
    result = gemini_json(prompt)
    if isinstance(result, dict) and "note" in result:
        return result

    # Fallback editorial note
    today_str = datetime.now().strftime("%B %d, %Y")
    return {
        "summary": f"Good morning. Here is your Folio edition for {today_str}.",
        "note": (
            f"Good morning. Today's edition is anchored by developments in {lead.get('topic', 'global affairs')}, "
            f"specifically '{lead_title}'. As you scan through today's curated selections, notice how emerging technological shifts "
            f"and economic dynamics intersect. We have arranged today's stories to provide clear context without the noise."
        ),
        "parsed": {
            "primary_theme": f"{lead.get('topic', 'General').capitalize()} and Global Perspectives",
            "reading_time_minutes": 6,
            "key_takeaways": [
                f"Lead analysis on: {lead_title}",
                "Curated signals across science, industry, and culture"
            ]
        }
    }


def generate_daily_edition(
    user_id: str,
    edition_date: Optional[str] = None,
    force_fetch: bool = False
) -> Dict[str, Any]:
    """
    Orchestrates the complete daily newspaper edition generation pipeline:
    1. Fetches user profile and weights.
    2. Ingests fresh articles if pool is empty or force_fetch is requested.
    3. Scores articles for user.
    4. Curates edition sections (Lead, Focus, World, Briefs, Serendipity).
    5. Writes personal Editor's Note.
    6. Persists edition to Supabase.
    """
    today_date = edition_date or datetime.now().strftime("%Y-%m-%d")
    user = get_or_create_user(user_id)

    # 1. Check existing articles in database
    recent_articles = get_recent_articles(limit=50)

    # If few articles exist, automatically trigger an ingestion run
    if len(recent_articles) < 8 or force_fetch:
        logger.info("Article pool is low; triggering RSS ingestion...")
        ingest_all_sources(max_per_source=4)
        recent_articles = get_recent_articles(limit=60)

    if not recent_articles:
        logger.warning("No articles available even after fetch.")
        # Minimal mock fallback article to ensure edition generation never crashes
        recent_articles = [{
            "id": "folio-welcome-story",
            "title": "Welcome to Folio: Your Personalized Morning Paper",
            "link": "https://folio-paper.app",
            "source": "Folio Editorial",
            "summary": "Folio curates the daily news according to your intellectual interests, cutting through sensationalism with editorial rigor.",
            "ai_summary": "Folio delivers an ad-free, high-signal newspaper customized to your cognitive depth and reading rhythm.",
            "topic": "culture",
            "image_url": "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=1200&auto=format&fit=crop",
            "tone": "informative",
            "cluster_id": "welcome-cluster",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }]

    # 2. Score candidate articles
    scored_articles = score_articles_for_user(recent_articles, user_id)

    # 3. Curate layout & sections
    curated = rank_and_curate_edition(scored_articles, user)

    # 4. Generate Editor's Note
    editor_note_data = compose_editor_note(user, curated)

    # Save editor note to database
    save_editor_note(
        user_id=user_id,
        note=editor_note_data.get("note", ""),
        parsed=editor_note_data.get("parsed", {}),
        summary=editor_note_data.get("summary", "")
    )

    # 5. Assemble edition content
    edition_content = {
        "masthead": {
            "title": "FOLIO",
            "tagline": "The Personalized Morning Chronicle",
            "edition_date": today_date,
            "user_id": user_id,
            "visual_mode": user.get("visual_mode", "broadsheet"),
            "language": user.get("language", "en"),
            "reading_time": editor_note_data.get("parsed", {}).get("reading_time_minutes", 6)
        },
        "editor_note": editor_note_data,
        "lead": curated.get("lead"),
        "focus": curated.get("focus", []),
        "world_society": curated.get("world_society", []),
        "serendipity": curated.get("serendipity"),
        "briefs": curated.get("briefs", []),
        "all_articles": curated.get("all_articles", []),
        "stats": curated.get("stats", {})
    }

    # 6. Save edition to Supabase
    saved_edition = save_edition(user_id, today_date, edition_content)

    return saved_edition or {
        "id": "temp-edition-id",
        "user_id": user_id,
        "edition_date": today_date,
        "content": edition_content,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
