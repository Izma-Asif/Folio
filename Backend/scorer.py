import math
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db import get_user, get_topic_weights, get_or_create_user
from ai import gemini_json

logger = logging.getLogger("folio.scorer")


def calculate_recency_score(published_at_str: Optional[str], half_life_hours: float = 24.0) -> float:
    """Calculates an exponential recency decay score between 0.1 and 1.0."""
    if not published_at_str:
        return 0.5

    try:
        if published_at_str.endswith("Z"):
            published_at_str = published_at_str[:-1] + "+00:00"
        pub_dt = datetime.fromisoformat(published_at_str)
        now_dt = datetime.now(timezone.utc)
        hours_old = max(0.0, (now_dt - pub_dt).total_seconds() / 3600.0)

        # Exponential decay: score = 2^(-hours / half_life)
        decay = math.pow(0.5, hours_old / half_life_hours)
        return max(0.1, min(1.0, decay))
    except Exception as e:
        logger.debug(f"Error parsing date {published_at_str}: {e}")
        return 0.5


def evaluate_depth_match(user_depth: str, summary_text: str) -> float:
    """Evaluates how well article summary length/depth matches user preference."""
    word_count = len(summary_text.split())
    
    if user_depth == "overview":
        # Prefers succinct, compact summaries
        return 1.2 if word_count < 60 else 0.8
    elif user_depth == "deep" or user_depth == "in-depth":
        # Prefers rich, detailed reporting
        return 1.2 if word_count > 80 else 0.9
    else:  # balanced
        return 1.0


def score_article(
    article: Dict[str, Any],
    user_profile: Dict[str, Any],
    topic_weights: Dict[str, float]
) -> Dict[str, Any]:
    """
    Computes a personalized relevance score for an article.
    Factors in topic weights, recency decay, calm mode, and depth preferences.
    """
    topic = (article.get("topic") or "world").lower().strip()
    title = article.get("title", "")
    summary = article.get("summary", "") or article.get("ai_summary", "")
    tone = (article.get("tone") or "neutral").lower()

    # 1. Base topic weight (default is 1.0)
    topic_weight = topic_weights.get(topic, 1.0)

    # 2. Direct interest match bonus
    user_interests = [i.lower() for i in (user_profile.get("interests") or [])]
    interest_bonus = 0.3 if topic in user_interests else 0.0

    # 3. Recency score (0.1 to 1.0)
    recency_score = calculate_recency_score(article.get("published_at"))

    # 4. Depth match multiplier
    user_depth = user_profile.get("depth", "balanced")
    depth_multiplier = evaluate_depth_match(user_depth, summary)

    # 5. Calm mode adjustment
    calm_mode = user_profile.get("calm_mode", False)
    calm_factor = 1.0
    if calm_mode:
        if tone in ("urgent", "critical"):
            calm_factor = 0.6  # De-escalate alarmist reporting
        elif tone in ("informative", "neutral"):
            calm_factor = 1.2  # Elevate grounded reporting

    # Combined score formula
    raw_score = (topic_weight + interest_bonus) * (0.6 * recency_score + 0.4) * depth_multiplier * calm_factor
    final_score = round(max(0.05, raw_score), 3)

    return {
        **article,
        "score": final_score,
        "score_breakdown": {
            "topic_weight": topic_weight,
            "interest_bonus": interest_bonus,
            "recency_score": round(recency_score, 3),
            "depth_multiplier": depth_multiplier,
            "calm_factor": calm_factor,
        }
    }


def score_articles_for_user(articles: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
    """
    Scores and ranks candidate articles specifically for the specified user.
    """
    user = get_or_create_user(user_id)
    weights = get_topic_weights(user_id)

    scored_articles = []
    for art in articles:
        scored = score_article(art, user, weights)
        scored_articles.append(scored)

    # Sort descending by score
    scored_articles.sort(key=lambda x: x.get("score", 0), reverse=True)
    return scored_articles
