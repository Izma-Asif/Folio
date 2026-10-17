import logging
from typing import Any, Dict, List, Optional

from db import (
    log_event,
    get_article,
    get_topic_weights,
    update_topic_weight,
    get_user_events,
)
from ai import gemini_json

logger = logging.getLogger("folio.learner")

# Weight adjustment deltas for various interaction events
EVENT_WEIGHT_DELTAS: Dict[str, float] = {
    "thumbs_up": 0.35,
    "bookmark": 0.30,
    "save": 0.30,
    "read": 0.15,
    "dwell_long": 0.20,
    "open": 0.05,
    "skim": 0.02,
    "thumbs_down": -0.40,
    "skip": -0.10,
    "hide": -0.25,
}

MIN_WEIGHT = 0.1
MAX_WEIGHT = 5.0


def clamp_weight(weight: float) -> float:
    """Restricts weight value within acceptable bounds."""
    return round(max(MIN_WEIGHT, min(MAX_WEIGHT, weight)), 3)


def adjust_topic_weight(user_id: str, topic: str, delta: float) -> float:
    """Adjusts a specific topic's weight by delta and saves to database."""
    weights = get_topic_weights(user_id)
    clean_topic = topic.lower().strip()
    current_weight = weights.get(clean_topic, 1.0)
    new_weight = clamp_weight(current_weight + delta)
    update_topic_weight(user_id, clean_topic, new_weight)
    return new_weight


def analyze_feedback_with_ai(reason: str, article_title: str) -> Optional[Dict[str, Any]]:
    """
    Uses gemini_json to parse nuanced reader feedback into specific topic adjustments.
    """
    prompt = f"""
Reader provided feedback on the news article: "{article_title}".
Reader feedback: "{reason}"

Determine which topic or interest should be adjusted and by how much (-0.5 to +0.5).
Return JSON with keys:
- "topic": canonical topic name or tag
- "suggested_delta": float between -0.5 and 0.5
"""
    result = gemini_json(prompt)
    if isinstance(result, dict) and "topic" in result and "suggested_delta" in result:
        return result
    return None


def record_interaction(
    user_id: str,
    article_id: Optional[str],
    event_type: str,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    Logs an interaction event and updates user's personalized topic weights.
    """
    clean_event = event_type.lower().strip()
    logged = log_event(user_id, article_id, clean_event, reason)

    updated_topic = None
    new_weight = None

    if article_id:
        article = get_article(article_id)
        if article:
            topic = (article.get("topic") or "world").lower().strip()
            delta = EVENT_WEIGHT_DELTAS.get(clean_event, 0.0)

            # Check if user provided custom text feedback (e.g., "Too much political noise")
            if reason:
                ai_adjust = analyze_feedback_with_ai(reason, article.get("title", ""))
                if ai_adjust:
                    custom_topic = ai_adjust.get("topic")
                    custom_delta = float(ai_adjust.get("suggested_delta", 0.0))
                    if custom_topic and custom_delta != 0:
                        topic = custom_topic
                        delta = custom_delta

            if delta != 0.0:
                new_weight = adjust_topic_weight(user_id, topic, delta)
                updated_topic = topic

    return {
        "event": logged,
        "updated_topic": updated_topic,
        "new_weight": new_weight
    }


def get_user_learning_profile(user_id: str) -> Dict[str, Any]:
    """
    Summarizes user's learned preferences and recent event history.
    """
    weights = get_topic_weights(user_id)
    recent_events = get_user_events(user_id, limit=30)

    # Sort topics by weight
    sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)

    return {
        "user_id": user_id,
        "topic_weights": dict(sorted_weights),
        "top_topics": [t[0] for t in sorted_weights[:3]],
        "deprioritized_topics": [t[0] for t in sorted_weights if t[1] < 0.8],
        "recent_event_count": len(recent_events),
        "recent_events": recent_events[:10]
    }
