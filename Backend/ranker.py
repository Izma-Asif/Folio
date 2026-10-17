import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("folio.ranker")


def deduplicate_clusters(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filters out duplicate coverage of the same news cluster, keeping the highest-scored one."""
    seen_clusters: Set[str] = set()
    unique_articles: List[Dict[str, Any]] = []

    for art in articles:
        cluster_id = art.get("cluster_id")
        if cluster_id:
            if cluster_id in seen_clusters:
                continue
            seen_clusters.add(cluster_id)
        unique_articles.append(art)

    return unique_articles


def get_target_article_count(user_length_pref: str) -> int:
    """Returns total articles to include based on user's desired paper length."""
    if user_length_pref == "short":
        return 6
    elif user_length_pref == "long":
        return 14
    return 10  # default medium


def rank_and_curate_edition(
    scored_articles: List[Dict[str, Any]],
    user_profile: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Ranks articles and constructs an editorial layout for a daily newspaper:
    - Lead Story (Front page headline)
    - Focus / Deep Dives (Primary interest topics)
    - World & Pulse (Broad perspective)
    - Briefs & Signals (Quick reads)
    - Serendipity (Discovery story outside user bubble)
    """
    # 1. Cluster deduplication
    candidates = deduplicate_clusters(scored_articles)

    if not candidates:
        return {
            "lead": None,
            "focus": [],
            "world_society": [],
            "briefs": [],
            "serendipity": None,
            "all_articles": [],
            "stats": {"total": 0}
        }

    user_length = user_profile.get("length", "medium")
    max_total = get_target_article_count(user_length)
    user_interests = set(i.lower() for i in (user_profile.get("interests") or []))

    # 2. Pick Lead Story: highest overall score, prefer with image
    lead_story = candidates[0]
    # Check if top 3 has one with an image
    for art in candidates[:3]:
        if art.get("image_url"):
            lead_story = art
            break

    remaining = [a for a in candidates if a["id"] != lead_story["id"]]

    # 3. Focus Stories (matching user interests)
    focus_stories: List[Dict[str, Any]] = []
    other_stories: List[Dict[str, Any]] = []

    for art in remaining:
        topic = (art.get("topic") or "").lower()
        if topic in user_interests and len(focus_stories) < 3:
            focus_stories.append(art)
        else:
            other_stories.append(art)

    remaining_pool = [a for a in remaining if a not in focus_stories]

    # 4. Serendipity Story (article from a topic outside user's top interests to broaden horizon)
    serendipity_story: Optional[Dict[str, Any]] = None
    for art in remaining_pool:
        topic = (art.get("topic") or "").lower()
        if topic not in user_interests:
            serendipity_story = art
            remaining_pool.remove(art)
            break

    # 5. World & Society / General Pulse
    world_stories = remaining_pool[:3]
    remaining_pool = remaining_pool[3:]

    # 6. Briefs & Signals
    briefs_needed = max(1, max_total - (1 + len(focus_stories) + len(world_stories) + (1 if serendipity_story else 0)))
    briefs = remaining_pool[:briefs_needed]

    # Combine all selected articles with their assigned editorial sections
    all_selected: List[Dict[str, Any]] = []

    lead_story_assigned = {**lead_story, "editorial_section": "lead"}
    all_selected.append(lead_story_assigned)

    for art in focus_stories:
        all_selected.append({**art, "editorial_section": "focus"})

    for art in world_stories:
        all_selected.append({**art, "editorial_section": "world"})

    if serendipity_story:
        all_selected.append({**serendipity_story, "editorial_section": "serendipity"})

    for art in briefs:
        all_selected.append({**art, "editorial_section": "briefs"})

    return {
        "lead": lead_story_assigned,
        "focus": [{**a, "editorial_section": "focus"} for a in focus_stories],
        "world_society": [{**a, "editorial_section": "world"} for a in world_stories],
        "serendipity": {**serendipity_story, "editorial_section": "serendipity"} if serendipity_story else None,
        "briefs": [{**a, "editorial_section": "briefs"} for a in briefs],
        "all_articles": all_selected,
        "stats": {
            "total_articles": len(all_selected),
            "lead_topic": lead_story.get("topic"),
            "section_distribution": {
                "lead": 1,
                "focus": len(focus_stories),
                "world": len(world_stories),
                "serendipity": 1 if serendipity_story else 0,
                "briefs": len(briefs),
            }
        }
    }
