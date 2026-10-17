import re
import json
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from ai import gemini_json
from angles import extract_cluster_angles
from db import (
    get_supabase,
    get_user,
    get_or_create_user,
    get_topic_weights,
    DEFAULT_USER_ID,
)

logger = logging.getLogger("folio.ranker")

# Source credibility / quality scores (default is 0.5)
SOURCE_QUALITY: Dict[str, float] = {
    "dawn": 0.90,
    "express tribune": 0.85,
    "propakistani": 0.80,
    "bbc world": 0.95,
    "al jazeera": 0.90,
    "bbc business": 0.90,
    "techcrunch": 0.88,
    "the verge": 0.88,
    "hacker news": 0.85,
    "bbc sport": 0.90,
    "espncricinfo": 0.92,
    "nasa": 0.98,
    "nature news": 0.98,
    "bbc health": 0.92,
    "bbc entertainment": 0.85
}


def get_source_quality(source_name: Optional[str]) -> float:
    """Returns source quality score between 0.0 and 1.0."""
    if not source_name:
        return 0.5
    clean_src = source_name.lower().strip()
    if clean_src in SOURCE_QUALITY:
        return SOURCE_QUALITY[clean_src]
    for k, v in SOURCE_QUALITY.items():
        if k in clean_src:
            return v
    return 0.5


def calculate_freshness(published_at_str: Optional[str], now_dt: datetime) -> float:
    """Calculates freshness score: 1.0 when brand new, fading linearly to 0.0 at 48 hours."""
    if not published_at_str:
        return 0.5
    try:
        if published_at_str.endswith("Z"):
            published_at_str = published_at_str[:-1] + "+00:00"
        pub_dt = datetime.fromisoformat(published_at_str)
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        hours_old = max(0.0, (now_dt - pub_dt).total_seconds() / 3600.0)
        return max(0.0, min(1.0, 1.0 - (hours_old / 48.0)))
    except Exception:
        return 0.5


def get_user_saved_interactions(user_id: str, now_dt: datetime) -> Dict[str, int]:
    """
    Returns mapping of topic.lower() -> count of saved/clicked articles in the last 14 days.
    """
    client = get_supabase()
    cutoff_14d = (now_dt - timedelta(days=14)).isoformat()
    topic_counts: Dict[str, int] = {}

    try:
        # Query saved/read events in last 14 days
        res = client.table("events").select("article_id, type").eq("user_id", user_id).gte("created_at", cutoff_14d).execute()
        events = res.data or []
        relevant_article_ids = list(set(
            e["article_id"] for e in events
            if e.get("article_id") and e.get("type") in ("bookmark", "save", "read", "click", "open", "dwell_long", "thumbs_up")
        ))

        if relevant_article_ids:
            # Fetch topics for these interacted articles
            art_res = client.table("articles").select("topic").in_("id", relevant_article_ids[:100]).execute()
            for row in (art_res.data or []):
                t = (row.get("topic") or "").lower().strip()
                if t:
                    topic_counts[t] = topic_counts.get(t, 0) + 1
    except Exception as e:
        logger.debug(f"Error fetching saved interactions for {user_id}: {e}")

    return topic_counts


def get_recent_editor_note_requests(user_id: str) -> List[str]:
    """Fetches recent user preference notes from editor_notes to personalize 'why' text."""
    client = get_supabase()
    requests = []
    try:
        res = client.table("editor_notes").select("note, summary").eq("user_id", user_id).order("created_at", desc=True).limit(2).execute()
        for r in (res.data or []):
            text = (r.get("note") or "") + " " + (r.get("summary") or "")
            if text:
                requests.append(text.lower())
    except Exception as e:
        logger.debug(f"Error fetching editor notes: {e}")
    return requests


def generate_article_why(
    article: Dict[str, Any],
    user_interests: Set[str],
    saved_counts: Dict[str, int],
    editor_requests: List[str],
    is_explore: bool = False
) -> str:
    """Generates personalized justification for why this article was included."""
    topic = (article.get("topic") or "World").strip()
    topic_lower = topic.lower()

    if is_explore:
        return f"Outside your usual topics • Explore {topic}"

    # Check recent editor notes (e.g., "You asked for more startups")
    for req in editor_requests:
        if topic_lower in req or (topic_lower == "tech" and "startup" in req):
            return f"You asked for more {topic}"

    # Check if saved in last 14 days
    saved_count = saved_counts.get(topic_lower, 0)
    if saved_count > 0:
        return f"Because you saved {saved_count} {topic} stories"

    # Check if in user's top interests
    if topic_lower in user_interests:
        return f"Because you follow {topic}"

    return f"Curated for you in {topic}"


def generate_three_things(top_articles: List[Dict[str, Any]], user_depth: str) -> List[str]:
    """Generates 3 short takeaways from top stories using Gemini (with fallback)."""
    if not top_articles:
        return [
            "Global developments in technology and science continue to advance rapidly.",
            "Policy makers and regional authorities announce strategic priorities for the coming quarter.",
            "Key market indicators reflect shifting international consumer trends."
        ]

    top_text_blocks = []
    for idx, art in enumerate(top_articles[:4], 1):
        summary = art.get("ai_summary") or art.get("summary") or ""
        top_text_blocks.append(f"{idx}. {art.get('title')} ({art.get('topic')}) - {summary}")

    simplicity_instruction = (
        "Explain in very simple, jargon-free terms accessible to a general reader."
        if user_depth in ("beginner", "overview")
        else "Provide substantive, sharp analytical takeaways."
    )

    prompt = f"""You are the Editor-in-Chief of Folio.
Based on today's top stories below, write exactly 3 punchy, high-signal takeaway bullets capturing the essence of today's news.
{simplicity_instruction}

Top Stories:
{chr(10).join(top_text_blocks)}

Return a valid JSON array of exactly 3 concise strings:
["Takeaway 1...", "Takeaway 2...", "Takeaway 3..."]"""

    res = gemini_json(prompt)
    if isinstance(res, list) and len(res) == 3 and all(isinstance(x, str) for x in res):
        return [str(x).strip() for x in res]
    elif isinstance(res, dict) and "takeaways" in res and isinstance(res["takeaways"], list):
        items = [str(x).strip() for x in res["takeaways"][:3]]
        if len(items) == 3:
            return items

    # Fallback heuristic takeaways
    fallbacks = []
    for art in top_articles[:3]:
        summary = art.get("ai_summary") or art.get("summary") or art.get("title")
        first_sentence = summary.split(". ")[0].strip()
        if not first_sentence.endswith("."):
            first_sentence += "."
        fallbacks.append(f"{art.get('topic')}: {first_sentence}")

    while len(fallbacks) < 3:
        fallbacks.append("Key international developments continue to unfold across major sectors.")

    return fallbacks[:3]


def compute_edition_changes(
    current_articles: List[Dict[str, Any]],
    user_id: str,
    today_date: str
) -> List[str]:
    """
    Compares current edition topic distribution with user's previous edition
    (either today's pre-regeneration edition or an earlier edition) and incorporates
    any recent AI Editor note to produce 2 to 4 plain sentences explaining shifts.
    """
    client = get_supabase()

    # 1. Fetch recent editor notes from the last 24h for context
    recent_note_summary = None
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        notes_res = (
            client.table("editor_notes")
            .select("summary, note")
            .eq("user_id", user_id)
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if notes_res.data and len(notes_res.data) > 0:
            recent_note_summary = notes_res.data[0].get("summary") or notes_res.data[0].get("note")
    except Exception as e:
        logger.debug(f"Error fetching recent editor note for changes: {e}")

    # 2. Find previous edition:
    # First check if an edition already exists for today (regeneration)
    prev_content = None
    try:
        existing_today = (
            client.table("editions")
            .select("content")
            .eq("user_id", user_id)
            .eq("edition_date", today_date)
            .execute()
        )
        if existing_today.data and len(existing_today.data) > 0:
            prev_content = existing_today.data[0].get("content") or {}
        else:
            # Check previous date edition
            prev_date_res = (
                client.table("editions")
                .select("content, edition_date")
                .eq("user_id", user_id)
                .neq("edition_date", today_date)
                .order("edition_date", desc=True)
                .limit(1)
                .execute()
            )
            if prev_date_res.data and len(prev_date_res.data) > 0:
                prev_content = prev_date_res.data[0].get("content") or {}
    except Exception as e:
        logger.debug(f"Error fetching previous edition for changes comparison: {e}")

    if not prev_content and not recent_note_summary:
        return []

    sentences = []
    if recent_note_summary:
        clean_note = recent_note_summary.strip()
        if not clean_note.endswith("."):
            clean_note += "."
        sentences.append(f"Editor update: {clean_note}")

    if prev_content:
        # Count current topics
        curr_counts: Dict[str, int] = {}
        for a in current_articles:
            t = (a.get("topic") or "World").capitalize()
            curr_counts[t] = curr_counts.get(t, 0) + 1

        # Count previous topics
        prev_counts: Dict[str, int] = {}
        prev_lead = prev_content.get("lead")
        if prev_lead and prev_lead.get("topic"):
            pt = prev_lead["topic"].capitalize()
            prev_counts[pt] = prev_counts.get(pt, 0) + 1

        for sec in prev_content.get("sections", []):
            for a in sec.get("articles", []):
                pt = (a.get("topic") or sec.get("topic") or "World").capitalize()
                prev_counts[pt] = prev_counts.get(pt, 0) + 1

        for a in prev_content.get("explore", []):
            pt = (a.get("topic") or "World").capitalize()
            prev_counts[pt] = prev_counts.get(pt, 0) + 1

        # Compute differences
        all_topics = set(curr_counts.keys()) | set(prev_counts.keys())
        diffs = []
        for t in all_topics:
            c = curr_counts.get(t, 0)
            p = prev_counts.get(t, 0)
            diff = c - p
            if diff != 0:
                diffs.append((t, diff, c, p))

        diffs.sort(key=lambda x: abs(x[1]), reverse=True)
        for t, diff, c, p in diffs[:3]:
            if diff > 0:
                sentences.append(f"{diff} more {t} {'story was' if diff == 1 else 'stories were'} added to your lineup.")
            else:
                sentences.append(f"{abs(diff)} fewer {t} {'story was' if abs(diff) == 1 else 'stories were'} featured in this reprint.")

    if not sentences and prev_content:
        sentences.append("Edition reprinted with refreshed story rankings based on your latest signals.")

    return sentences[:4]


def format_article_for_edition(
    article: Dict[str, Any],
    why: str,
    also_covered_by: List[str],
    angles: List[Dict[str, str]]
) -> Dict[str, Any]:
    """Ensures article dictionary exactly adheres to the required Edition Article schema."""
    summary = article.get("ai_summary") or article.get("summary") or ""
    return {
        "id": str(article["id"]),
        "title": str(article.get("title", "")).strip(),
        "link": str(article.get("link", "")).strip(),
        "source": str(article.get("source", "")).strip(),
        "summary": summary,
        "topic": (article.get("topic") or "World").strip(),
        "image_url": article.get("image_url"),
        "why": why,
        "also_covered_by": also_covered_by,
        "tone": str(article.get("tone") or "neutral"),
        "angles": angles
    }


# ---------------------------------------------------------------------------
# MAIN EDITION BUILDER
# ---------------------------------------------------------------------------

def build_edition(user_id: str, edition_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Builds a finite, publication-ready daily newspaper edition for user_id:
    1. Scores articles from the last 48 hours using:
       score = 0.5*topic_weight + 0.2*freshness + 0.15*source_quality + 0.15*similarity_to_saved
    2. Cluster deduplication: keeps best article per cluster_id, attaches also_covered_by & angles.
    3. Calm mode filtering: drops heavy articles, boosts light ones.
    4. Lead story selection: highest scoring article.
    5. Curates 4-5 sections (3-4 articles each) from highest topic weights.
    6. Reserves 2 explore articles from low-weight topics.
    7. Respects length preference (short: ~10 articles; default: 15-20 articles).
    8. Generates 'why', 'three_things', 'masthead', 'read_minutes', and 'changes'.
    9. Saves into Supabase editions table (replaces today's edition if it exists).
    """
    client = get_supabase()
    now_dt = datetime.now(timezone.utc)
    today_date = edition_date or now_dt.strftime("%Y-%m-%d")

    # 1. Fetch user settings and topic weights
    user = get_or_create_user(user_id)
    weights = get_topic_weights(user_id)
    user_interests_set = set(i.lower().strip() for i in (user.get("interests") or []))
    calm_mode = user.get("calm_mode", False)
    length_pref = (user.get("length") or "medium").lower()
    depth_pref = (user.get("depth") or "balanced").lower()

    # Target article counts
    is_short = (length_pref == "short")
    target_sections_count = 3 if is_short else 4
    target_per_section = 2 if is_short else 3
    max_total_articles = 10 if is_short else 18

    # 2. Fetch candidate articles from last 48 hours
    cutoff_48h = (now_dt - timedelta(hours=48)).isoformat()
    try:
        res = client.table("articles").select("*").gte("published_at", cutoff_48h).execute()
        raw_candidates = res.data or []
    except Exception as e:
        logger.warning(f"Error fetching 48h articles: {e}")
        raw_candidates = []

    # If pool is sparse, fetch recent articles by created_at to guarantee paper completeness
    if len(raw_candidates) < 15:
        fallback_res = client.table("articles").select("*").order("created_at", desc=True).limit(60).execute()
        raw_candidates = fallback_res.data or []

    # 3. Retrieve user saved interactions & editor notes
    saved_topic_counts = get_user_saved_interactions(user_id, now_dt)
    editor_requests = get_recent_editor_note_requests(user_id)

    # 4. Score each article
    scored_pool: List[Dict[str, Any]] = []
    for art in raw_candidates:
        topic = (art.get("topic") or "World").strip()
        topic_lower = topic.lower()

        # Score components
        topic_wt = weights.get(topic_lower, 0.3)
        freshness = calculate_freshness(art.get("published_at"), now_dt)
        source_qual = get_source_quality(art.get("source"))
        sim_saved = 1.0 if topic_lower in saved_topic_counts else 0.0

        # Exact formula: 0.5*topic_weight + 0.2*freshness + 0.15*source_quality + 0.15*similarity_to_saved
        base_score = (0.5 * topic_wt) + (0.2 * freshness) + (0.15 * source_qual) + (0.15 * sim_saved)

        tone = (art.get("tone") or "neutral").lower()

        # Calm mode adjustment
        if calm_mode:
            if tone == "heavy":
                base_score *= 0.30  # Heavily de-prioritize heavy tone
            elif tone == "light":
                base_score *= 1.25  # Boost light tone

        scored_art = dict(art)
        scored_art["_score"] = round(base_score, 4)
        scored_pool.append(scored_art)

    # 5. Cluster grouping: one article per cluster_id (keep best), gather also_covered_by & angles
    cluster_buckets: Dict[str, List[Dict[str, Any]]] = {}
    for art in scored_pool:
        cid = str(art.get("cluster_id") or art["id"])
        cluster_buckets.setdefault(cid, []).append(art)

    # Call Gemini once in batch for all clusters with 2 or more sources (skips silently on failure)
    ai_cluster_angles = extract_cluster_angles(cluster_buckets)

    deduped_candidates: List[Dict[str, Any]] = []
    for cid, members in cluster_buckets.items():
        # Sort members by score descending
        members.sort(key=lambda x: x["_score"], reverse=True)
        best = members[0]

        # Other sources in cluster
        other_sources = list(dict.fromkeys(
            m.get("source", "").strip() for m in members
            if m.get("source") and m.get("source") != best.get("source")
        ))

        # Distinct sources count across all members in this cluster
        distinct_sources = list(dict.fromkeys(
            m.get("source", "").strip() for m in members
            if m.get("source") and m.get("source").strip()
        ))

        # Only attach angles for clusters with 2 or more sources
        if len(distinct_sources) >= 2:
            # Use Gemini angles if available; otherwise skip (or empty list)
            cluster_angles = ai_cluster_angles.get(cid, [])
        else:
            cluster_angles = []

        best["_also_covered_by"] = other_sources
        best["_angles"] = cluster_angles
        deduped_candidates.append(best)

    # In calm_mode: drop heavy articles unless it has exceptional score
    if calm_mode:
        deduped_candidates = [
            a for a in deduped_candidates
            if (a.get("tone") != "heavy" or a["_score"] >= 0.75)
        ]

    # Sort deduped candidates by score descending
    deduped_candidates.sort(key=lambda x: x["_score"], reverse=True)

    if not deduped_candidates:
        # Fallback empty structure
        return {
            "id": str(uuid.uuid4()),
            "date": today_date,
            "masthead": "The Morning Folio",
            "read_minutes": 5,
            "lead": None,
            "sections": [],
            "explore": [],
            "three_things": [],
            "changes": []
        }

    # 6. Highest score = Lead Story
    lead_raw = deduped_candidates[0]
    lead_why = generate_article_why(lead_raw, user_interests_set, saved_topic_counts, editor_requests)
    lead_article = format_article_for_edition(
        lead_raw,
        why=lead_why,
        also_covered_by=lead_raw.get("_also_covered_by", []),
        angles=lead_raw.get("_angles", [])
    )

    remaining_pool = [a for a in deduped_candidates if a["id"] != lead_raw["id"]]

    # 7. Identify Top Topics for Sections (from highest topic weights)
    sorted_user_topics = [
        t.capitalize() for t, w in sorted(weights.items(), key=lambda x: x[1], reverse=True)
    ]
    # Filter to topics that have at least 1 article available
    available_topics = set(a.get("topic", "").capitalize() for a in remaining_pool if a.get("topic"))
    section_topics = [t for t in sorted_user_topics if t in available_topics][:target_sections_count]

    # If fewer than target sections, fill with most prevalent topics
    if len(section_topics) < target_sections_count:
        for t in available_topics:
            if t not in section_topics:
                section_topics.append(t)
            if len(section_topics) >= target_sections_count:
                break

    # Build sections
    sections_list: List[Dict[str, Any]] = []
    used_article_ids: Set[str] = {lead_raw["id"]}

    for topic_name in section_topics:
        topic_articles = [
            a for a in remaining_pool
            if (a.get("topic") or "").capitalize() == topic_name and a["id"] not in used_article_ids
        ][:target_per_section]

        if not topic_articles:
            continue

        formatted_section_articles = []
        for art in topic_articles:
            used_article_ids.add(art["id"])
            why_text = generate_article_why(art, user_interests_set, saved_topic_counts, editor_requests)
            formatted_art = format_article_for_edition(
                art,
                why=why_text,
                also_covered_by=art.get("_also_covered_by", []),
                angles=art.get("_angles", [])
            )
            formatted_section_articles.append(formatted_art)

        sections_list.append({
            "topic": topic_name,
            "articles": formatted_section_articles
        })

    # 8. Reserve 2 "explore" articles from low-weight topics
    high_weight_topics_set = set(t.lower() for t in section_topics)
    explore_candidates = [
        a for a in remaining_pool
        if a["id"] not in used_article_ids and (a.get("topic") or "").lower() not in high_weight_topics_set
    ]

    # If none found from outside high-weight topics, take from unused pool
    if not explore_candidates:
        explore_candidates = [a for a in remaining_pool if a["id"] not in used_article_ids]

    explore_raw = explore_candidates[:2]
    explore_articles: List[Dict[str, Any]] = []
    for art in explore_raw:
        used_article_ids.add(art["id"])
        why_text = generate_article_why(art, user_interests_set, saved_topic_counts, editor_requests, is_explore=True)
        explore_articles.append(format_article_for_edition(
            art,
            why=why_text,
            also_covered_by=art.get("_also_covered_by", []),
            angles=art.get("_angles", [])
        ))

    # All articles included in edition
    all_edition_articles = [lead_article]
    for sec in sections_list:
        all_edition_articles.extend(sec["articles"])
    all_edition_articles.extend(explore_articles)

    # 9. Compute read_minutes
    total_words = sum(len(a["summary"].split()) for a in all_edition_articles)
    read_minutes = max(3, min(15, round(total_words / 160.0)))

    # 10. Generate three_things
    three_things = generate_three_things(all_edition_articles, depth_pref)

    # 11. Compute changes vs previous edition
    changes = compute_edition_changes(all_edition_articles, user_id, today_date)

    # 12. Masthead
    visual_mode = user.get("visual_mode", "broadsheet").capitalize()
    masthead = f"The Morning Folio • {visual_mode} Edition"

    # 13. Assemble final edition payload
    edition_id = str(uuid.uuid4())
    edition_content = {
        "id": edition_id,
        "date": today_date,
        "masthead": masthead,
        "read_minutes": read_minutes,
        "lead": lead_article,
        "sections": sections_list,
        "explore": explore_articles,
        "three_things": three_things,
        "changes": changes
    }

    # 14. Save in editions table: replace today's edition if it exists
    try:
        # Check existing edition for today
        existing_res = client.table("editions").select("id").eq("user_id", user_id).eq("edition_date", today_date).execute()
        if existing_res.data and len(existing_res.data) > 0:
            existing_id = existing_res.data[0]["id"]
            edition_id = existing_id
            edition_content["id"] = existing_id
            client.table("editions").update({
                "content": edition_content,
                "created_at": now_dt.isoformat()
            }).eq("id", existing_id).execute()
            logger.info(f"Replaced today's edition {existing_id} for user {user_id}")
        else:
            client.table("editions").insert({
                "id": edition_id,
                "user_id": user_id,
                "edition_date": today_date,
                "content": edition_content,
                "created_at": now_dt.isoformat()
            }).execute()
            logger.info(f"Created new edition {edition_id} for user {user_id}")
    except Exception as e:
        logger.error(f"Error persisting edition to Supabase: {e}")

    return edition_content
