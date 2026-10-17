"""
learner.py – Folio online learning module.

Handles:
- record_interaction(): log event, adjust topic weight with exact deltas.
- decay(): nudge all topic weights 2 % toward 0.5 (called after each edition generation).
- get_user_learning_profile(): used by /api/users/{id}/learning.

Delta table (spec):
  click          +0.05
  save           +0.15
  skip / not_interested  -0.20
  skip / already_know    -0.05
  skip / too_negative    -0.10  + calm_mode trigger after 3 in 7 days

Weights are clamped to [0.05, 1.0].
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from db import (
    get_supabase,
    log_event,
    get_article,
    get_topic_weights,
    update_topic_weight,
    update_user_preferences,
    get_user_events,
)

logger = logging.getLogger("folio.learner")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_WEIGHT = 0.05
MAX_WEIGHT = 1.0
DECAY_RATE = 0.02          # 2 % toward 0.5 per edition
DECAY_TARGET = 0.5
CALM_MODE_THRESHOLD = 3    # too_negative skips in 7 days → auto calm_mode


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def clamp_weight(w: float) -> float:
    """Clamp weight to [MIN_WEIGHT, MAX_WEIGHT] and round to 4 dp."""
    return round(max(MIN_WEIGHT, min(MAX_WEIGHT, w)), 4)


def _get_delta(event_type: str, reason: Optional[str]) -> float:
    """
    Returns the weight delta for the given event + optional reason.

    click           → +0.05
    save            → +0.15
    skip (default)  → -0.10
    skip + not_interested → -0.20
    skip + already_know   → -0.05
    skip + too_negative   → -0.10
    """
    et = (event_type or "").lower().strip()
    rs = (reason or "").lower().strip()

    if et == "click":
        return 0.05
    if et == "save":
        return 0.15
    if et == "skip":
        if rs == "not_interested":
            return -0.20
        if rs == "already_know":
            return -0.05
        # too_negative or unspecified skip
        return -0.10
    # Unknown event type → no change
    return 0.0


def _check_and_set_calm_mode(user_id: str) -> bool:
    """
    If the user has logged ≥3 'skip'+'too_negative' events in the last 7 days,
    set calm_mode = True on their profile.  Returns True if calm_mode was activated.
    """
    client = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        res = (
            client.table("events")
            .select("id")
            .eq("user_id", user_id)
            .eq("type", "skip")
            .eq("reason", "too_negative")
            .gte("created_at", cutoff)
            .execute()
        )
        count = len(res.data or [])
        if count >= CALM_MODE_THRESHOLD:
            update_user_preferences(user_id, {"calm_mode": True})
            logger.info(
                f"calm_mode auto-enabled for {user_id} "
                f"({count} too_negative skips in 7 days)"
            )
            return True
    except Exception as e:
        logger.debug(f"_check_and_set_calm_mode error: {e}")
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_interaction(
    user_id: str,
    article_id: Optional[str],
    event_type: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    1. Persist the event to the events table.
    2. Look up the article's topic.
    3. Apply the appropriate weight delta.
    4. If skip+too_negative, check calm_mode threshold.
    5. Return a summary dict.
    """
    et = (event_type or "").lower().strip()

    # 1. Persist event
    logged = log_event(user_id, article_id, et, reason)

    updated_topic: Optional[str] = None
    new_weight: Optional[float] = None
    calm_mode_triggered = False

    if article_id:
        article = get_article(article_id)
        if article:
            topic = (article.get("topic") or "world").lower().strip()
            delta = _get_delta(et, reason)

            if delta != 0.0:
                weights = get_topic_weights(user_id)
                # Default starting weight 0.5 (neutral) if topic not yet tracked
                current = weights.get(topic, 0.5)
                new_w = clamp_weight(current + delta)
                update_topic_weight(user_id, topic, new_w)
                updated_topic = topic
                new_weight = new_w
                logger.info(
                    f"record_interaction: user={user_id} topic={topic} "
                    f"event={et} reason={reason} Δ={delta:+.2f} "
                    f"{current:.4f}→{new_w:.4f}"
                )

    # too_negative calm_mode check: set calm_mode true if it happens 3 times in 7 days
    if et == "skip" and (reason or "").lower().strip() == "too_negative":
        calm_mode_triggered = _check_and_set_calm_mode(user_id)

    return {
        "event": logged,
        "updated_topic": updated_topic,
        "new_weight": new_weight,
        "calm_mode_triggered": calm_mode_triggered,
    }


def decay(user_id: str) -> Dict[str, float]:
    """
    Nudge every topic weight 2 % toward 0.5.
    Formula:  new = old + DECAY_RATE * (0.5 - old)
              = old * 0.98 + 0.5 * 0.02

    Called automatically inside ranker.build_edition() after saving each edition.
    Returns the updated weights dict.
    """
    weights = get_topic_weights(user_id)
    if not weights:
        return weights

    updated: Dict[str, float] = {}
    for topic, w in weights.items():
        new_w = clamp_weight(w + DECAY_RATE * (DECAY_TARGET - w))
        if new_w != w:
            update_topic_weight(user_id, topic, new_w)
        updated[topic] = new_w

    logger.debug(f"decay(): nudged {len(updated)} weights for user {user_id}")
    return updated


def get_user_learning_profile(user_id: str) -> Dict[str, Any]:
    """
    Full learning profile used by GET /api/users/{id}/learning.
    Returns weights, top topics, deprioritized topics, recent events.
    """
    weights = get_topic_weights(user_id)
    recent_events = get_user_events(user_id, limit=30)

    sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)

    return {
        "user_id": user_id,
        "topic_weights": dict(sorted_weights),
        "top_topics": [t for t, _ in sorted_weights[:3]],
        "deprioritized_topics": [t for t, w in sorted_weights if w < 0.4],
        "recent_event_count": len(recent_events),
        "recent_events": recent_events[:10],
    }
