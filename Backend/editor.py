"""
editor.py – Folio AI Editor-in-Chief module.

Handles:
- parse_editor_instruction(): sends plain-language reader feedback to Gemini
  along with ALLOWED_TOPICS to produce structured topic and setting adjustments.
- apply_editor_instruction(): applies the adjustments to topic_weights
  (clamped 0.05 to 1.0) and updates user settings (calm_mode, length, depth),
  saves note to editor_notes table, and returns {summary, applied}.
- get_user_editor_notes(): retrieves past notes from editor_notes.
"""

import logging
from typing import Any, Dict, List, Optional

from ai import gemini_json
from db import (
    get_supabase,
    get_or_create_user,
    get_topic_weights,
    update_topic_weight,
    update_user_preferences,
    save_editor_note,
)
from scorer import ALLOWED_TOPICS

logger = logging.getLogger("folio.editor")

MIN_WEIGHT = 0.05
MAX_WEIGHT = 1.0

# Canonical lowercase topic mapping for fuzzy / direct lookup
TOPIC_LOOKUP: Dict[str, str] = {t.lower(): t.lower() for t in ALLOWED_TOPICS}
# Common synonyms / subtopics
TOPIC_LOOKUP.update({
    "startups": "business",
    "startup": "business",
    "economy": "business",
    "markets": "business",
    "finance": "business",
    "geopolitics": "world",
    "international": "world",
    "global": "world",
    "technology": "tech",
    "gadgets": "tech",
    "coding": "tech",
    "software": "tech",
    "artificial intelligence": "ai",
    "machine learning": "ai",
    "football": "sports",
    "soccer": "sports",
    "tennis": "sports",
    "space": "science",
    "astronomy": "science",
    "environment": "climate",
    "global warming": "climate",
    "movies": "entertainment",
    "cinema": "entertainment",
    "music": "entertainment",
    "pop culture": "culture",
    "lifestyle": "culture",
})


def clamp_weight(w: float) -> float:
    """Clamp weight between 0.05 and 1.0, rounded to 4 decimal places."""
    return round(max(MIN_WEIGHT, min(MAX_WEIGHT, w)), 4)


def parse_editor_instruction(text: str) -> Dict[str, Any]:
    """
    Sends the user's plain-language instruction to Gemini with the current
    allowed topics list and returns structured adjustments.
    """
    topics_list_str = ", ".join(ALLOWED_TOPICS)

    prompt = f"""You are the Editor-in-Chief of "Folio", a personalized morning newspaper.
The reader just gave you this instruction for adjusting their newspaper preferences:
"{text}"

The allowed newspaper topics are:
{topics_list_str}

Analyze the reader's instruction and return ONLY a valid JSON object with these keys:
- "topic_adjustments": object mapping topic names (from the allowed list or close matches) to a float delta between -0.5 and +0.5 (e.g. {{"Politics": -0.3, "Tech": 0.2}}). If startups/finance is mentioned, adjust Business or Tech. If no topic adjustments are implied, return {{}}.
- "calm_mode": true if the user wants less negative/depressing/sad news or a calmer tone; false if they want raw/unfiltered news; null if not mentioned.
- "length": "short" if user wants briefer reads or mentions "keep it short" / "less reading"; "normal" if standard; null if not mentioned. Note: "keep it short on weekdays" should be treated as "short".
- "depth": "beginner" if user wants simple explanations or "explain like I'm new"; "normal" if standard/deep; null if not mentioned.
- "summary": one friendly, direct sentence describing what you changed in their editorial direction (e.g. "I've cut back on politics, boosted startup coverage, and tuned your daily paper for shorter reads.").

Examples:
- "less politics, more startups" -> {{"topic_adjustments": {{"Politics": -0.3, "Business": 0.2}}, "calm_mode": null, "length": null, "depth": null, "summary": "Reduced political coverage and added more business and startup news."}}
- "keep it short on weekdays" -> {{"topic_adjustments": {{}}, "calm_mode": null, "length": "short", "depth": null, "summary": "Set your edition length to short reads for a faster morning scan."}}
- "explain things like I'm new" -> {{"topic_adjustments": {{}}, "calm_mode": null, "length": null, "depth": "beginner", "summary": "Switched explanations to a beginner-friendly, accessible depth."}}
- "nothing too sad" -> {{"topic_adjustments": {{}}, "calm_mode": true, "length": null, "depth": null, "summary": "Enabled Calm Mode to filter out distressing and heavy stories."}}

Return ONLY valid JSON:
"""
    result = gemini_json(prompt)

    if isinstance(result, dict) and "summary" in result:
        return {
            "topic_adjustments": result.get("topic_adjustments") or {},
            "calm_mode": result.get("calm_mode"),
            "length": result.get("length"),
            "depth": result.get("depth"),
            "summary": str(result.get("summary", "")).strip(),
        }

    # Heuristic fallback if Gemini fails / rate limits
    text_lower = text.lower()
    adj: Dict[str, float] = {}
    calm: Optional[bool] = None
    length: Optional[str] = None
    depth: Optional[str] = None
    summary_parts: List[str] = []

    # Heuristic topic detection
    if "less politic" in text_lower or "no politic" in text_lower:
        adj["Politics"] = -0.3
        summary_parts.append("reduced politics")
    elif "more politic" in text_lower:
        adj["Politics"] = 0.2
        summary_parts.append("increased politics")

    if "more startup" in text_lower or "startups" in text_lower or "more business" in text_lower:
        adj["Business"] = 0.2
        summary_parts.append("boosted startup and business news")

    if "more tech" in text_lower:
        adj["Tech"] = 0.2
        summary_parts.append("boosted tech coverage")

    if "more cricket" in text_lower:
        adj["Cricket"] = 0.2
        summary_parts.append("boosted cricket coverage")

    if "less" in text_lower and not adj:
        for t in ALLOWED_TOPICS:
            if t.lower() in text_lower:
                adj[t] = -0.2
                summary_parts.append(f"reduced {t.lower()}")

    if "more" in text_lower and not any(v > 0 for v in adj.values()):
        for t in ALLOWED_TOPICS:
            if t.lower() in text_lower:
                adj[t] = 0.2
                summary_parts.append(f"increased {t.lower()}")

    # Heuristic calm mode
    if any(k in text_lower for k in ["sad", "calm", "too negative", "depressing", "peaceful"]):
        calm = True
        summary_parts.append("enabled Calm Mode")

    # Heuristic length
    if "short" in text_lower or "brief" in text_lower or "quick" in text_lower:
        length = "short"
        summary_parts.append("shortened edition length")

    # Heuristic depth
    if "new" in text_lower or "beginner" in text_lower or "simple" in text_lower:
        depth = "beginner"
        summary_parts.append("simplified depth for beginner-friendly reads")

    if summary_parts:
        summary_text = "I have " + ", ".join(summary_parts) + "."
    else:
        summary_text = "Updated your editorial preferences based on your note."

    return {
        "topic_adjustments": adj,
        "calm_mode": calm,
        "length": length,
        "depth": depth,
        "summary": summary_text,
    }


def apply_editor_instruction(user_id: str, text: str) -> Dict[str, Any]:
    """
    Parses instruction, applies topic adjustments (clamped 0.05-1.0),
    updates user profile settings (calm_mode, length, depth),
    saves to editor_notes table, and returns {summary, applied: parsed}.
    """
    get_or_create_user(user_id)
    parsed = parse_editor_instruction(text)

    topic_adjustments = parsed.get("topic_adjustments") or {}
    calm_mode = parsed.get("calm_mode")
    length = parsed.get("length")
    depth = parsed.get("depth")
    summary = parsed.get("summary") or "Applied your editorial instruction."

    # 1. Apply topic adjustments to topic_weights
    current_weights = get_topic_weights(user_id)
    applied_topic_changes = {}

    for raw_topic, delta in topic_adjustments.items():
        try:
            delta_val = float(delta)
        except (ValueError, TypeError):
            continue

        clean_topic = TOPIC_LOOKUP.get(raw_topic.lower().strip(), raw_topic.lower().strip())
        current_w = current_weights.get(clean_topic, 0.5)
        new_w = clamp_weight(current_w + delta_val)
        update_topic_weight(user_id, clean_topic, new_w)
        applied_topic_changes[clean_topic] = {
            "old": current_w,
            "new": new_w,
            "delta": delta_val,
        }

    # 2. Update user profile settings
    user_updates: Dict[str, Any] = {}
    if calm_mode is not None:
        user_updates["calm_mode"] = bool(calm_mode)
    if length in ("short", "normal"):
        user_updates["length"] = length
    if depth in ("beginner", "normal"):
        user_updates["depth"] = depth

    if user_updates:
        update_user_preferences(user_id, user_updates)

    # 3. Save into editor_notes table
    save_editor_note(
        user_id=user_id,
        note=text,
        parsed=parsed,
        summary=summary,
    )

    logger.info(
        f"apply_editor_instruction: user={user_id} topics_updated={len(applied_topic_changes)} "
        f"settings_updated={list(user_updates.keys())}"
    )

    return {
        "summary": summary,
        "applied": parsed,
    }


def list_user_editor_notes(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieves past editor notes for a user, ordered latest first."""
    client = get_supabase()
    try:
        res = (
            client.table("editor_notes")
            .select("id, user_id, note, parsed, summary, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error(f"list_user_editor_notes failed for {user_id}: {e}")
        return []
