import re
import json
import time
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set

from ai import gemini_json
from db import get_supabase, get_user, get_topic_weights, get_or_create_user

logger = logging.getLogger("folio.scorer")

# 13 Allowed topics as explicitly specified
ALLOWED_TOPICS: List[str] = [
    "Pakistan",
    "World",
    "Politics",
    "Business",
    "Tech",
    "AI",
    "Sports",
    "Cricket",
    "Science",
    "Health",
    "Entertainment",
    "Culture",
    "Climate"
]

ALLOWED_TOPICS_LOWER: Dict[str, str] = {t.lower(): t for t in ALLOWED_TOPICS}

# Feed default topic mapping for graceful fallbacks
SOURCE_TO_DEFAULT_TOPIC: Dict[str, str] = {
    "dawn": "Pakistan",
    "express tribune": "Pakistan",
    "propakistani": "Pakistan",
    "bbc world": "World",
    "al jazeera": "World",
    "bbc business": "Business",
    "techcrunch": "Tech",
    "the verge": "Tech",
    "hacker news": "Tech",
    "bbc sport": "Sports",
    "espncricinfo": "Cricket",
    "nasa": "Science",
    "nature news": "Science",
    "bbc health": "Health",
    "bbc entertainment": "Entertainment"
}

ALLOWED_TONES: Set[str] = {"light", "neutral", "heavy"}

HEAVY_KEYWORDS: Set[str] = {
    "war", "killed", "kill", "death", "dead", "fatal", "murder", "blast",
    "explosion", "bomb", "disaster", "earthquake", "flood", "crash",
    "casualt", "crisis", "attack", "hostage", "strike", "terror", "tragedy"
}

LIGHT_KEYWORDS: Set[str] = {
    "fun", "humor", "comedy", "celebrate", "cute", "whimsical", "game",
    "movie", "series", "music", "song", "viral", "festival", "award"
}

STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "can", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for",
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once",
    "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "would", "you", "your", "yours", "yourself", "yourselves", "says", "new", "will",
    "amid", "over", "also", "back", "first", "last", "two", "three", "year", "years", "day", "days"
}


def get_feed_default_topic(source_name: Optional[str]) -> str:
    """Finds matching default topic for source name, defaulting to World."""
    if not source_name:
        return "World"
    clean_src = source_name.lower().strip()
    if clean_src in SOURCE_TO_DEFAULT_TOPIC:
        return SOURCE_TO_DEFAULT_TOPIC[clean_src]

    # Partial match
    for k, v in SOURCE_TO_DEFAULT_TOPIC.items():
        if k in clean_src:
            return v
    return "World"


def extract_two_sentences(text: Optional[str]) -> str:
    """Extracts exactly two short neutral sentences from text."""
    if not text:
        return "No summary available."
    cleaned = re.sub(r"\s+", " ", text).strip()
    # Split on punctuation followed by space
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    if len(sentences) >= 2:
        return f"{sentences[0].strip()} {sentences[1].strip()}"
    elif len(sentences) == 1 and sentences[0]:
        s = sentences[0].strip()
        if not s.endswith((".", "!", "?")):
            s += "."
        return s
    return "No summary available."


def infer_fallback_tone(title: str, summary: str) -> str:
    """Infers tone (light | neutral | heavy) using heuristic keyword analysis."""
    combined = f"{title} {summary}".lower()
    for kw in HEAVY_KEYWORDS:
        if re.search(rf"\b{kw}", combined):
            return "heavy"
    for kw in LIGHT_KEYWORDS:
        if re.search(rf"\b{kw}", combined):
            return "light"
    return "neutral"


def normalize_topic(raw_topic: Optional[str], default_topic: str) -> str:
    """Normalizes string to one of the 13 canonical allowed topics."""
    if not raw_topic:
        return default_topic
    cleaned = raw_topic.strip().lower()
    if cleaned in ALLOWED_TOPICS_LOWER:
        return ALLOWED_TOPICS_LOWER[cleaned]
    # Check partial contains
    for k, canonical in ALLOWED_TOPICS_LOWER.items():
        if k in cleaned:
            return canonical
    return default_topic


def normalize_tone(raw_tone: Optional[str], fallback_tone: str) -> str:
    """Normalizes tone to 'light', 'neutral', or 'heavy'."""
    if not raw_tone:
        return fallback_tone
    cleaned = raw_tone.strip().lower()
    if cleaned in ALLOWED_TONES:
        return cleaned
    return fallback_tone


# ---------------------------------------------------------------------------
# SCORE NEW ARTICLES (BATCHES OF 10)
# ---------------------------------------------------------------------------

def score_new_articles() -> Dict[str, Any]:
    """
    Finds articles where topic is null and processes them in batches of 10 per API call.
    Returns for each article:
        - topic: one of [Pakistan, World, Politics, Business, Tech, AI, Sports, Cricket, Science, Health, Entertainment, Culture, Climate]
        - ai_summary: two short neutral sentences
        - tone: 'light' | 'neutral' | 'heavy' (heavy = war, death, disasters)
    Never crashes the batch if one item fails. Saves to articles table.
    If Gemini fails, falls back to the feed's default_topic and original summary.
    """
    client = get_supabase()
    
    # 1. Fetch articles where topic is null
    try:
        res = client.table("articles").select("id, title, summary, source, topic, tone").is_("topic", "null").order("created_at", desc=True).execute()
        unscored_articles = res.data or []
    except Exception as e:
        logger.error(f"Error fetching unscored articles: {e}")
        return {"articles_scored": 0, "batches_processed": 0, "error": str(e)}

    if not unscored_articles:
        logger.info("No articles with topic is null found.")
        return {
            "articles_scored": 0,
            "batches_processed": 0,
            "fallback_count": 0,
            "message": "No unscored articles found"
        }

    total_articles = len(unscored_articles)
    logger.info(f"Scoring {total_articles} unscored articles in batches of 10...")

    articles_scored = 0
    fallback_count = 0
    batches_processed = 0

    # 2. Process in batches of 10 per API call
    batch_size = 10
    for i in range(0, total_articles, batch_size):
        batch = unscored_articles[i:i + batch_size]
        batches_processed += 1

        batch_input = [
            {
                "id": str(art["id"]),
                "title": str(art.get("title", "")),
                "summary": str(art.get("summary", "") or "")[:350],
                "source": str(art.get("source", ""))
            }
            for art in batch
        ]

        prompt = f"""You are an expert newspaper editor. Categorize and summarize the following batch of {len(batch)} news articles.
For each article, analyze its title, source, and summary, and return a JSON list of objects.
Each object must have strictly these keys:
- "id": the exact article ID string provided
- "topic": strictly ONE of {ALLOWED_TOPICS}
- "ai_summary": exactly two short, objective, neutral sentences summarizing the news event
- "tone": strictly ONE of ["light", "neutral", "heavy"] ("heavy" is for war, deaths, violence, casualties, or major natural disasters; "light" is for entertaining, lifestyle, or uplifting stories; "neutral" for standard news)

Articles:
{json.dumps(batch_input, indent=2)}

Return a valid JSON array of objects with keys ["id", "topic", "ai_summary", "tone"]."""

        # Call Gemini using gemini_json
        gemini_response = gemini_json(prompt)

        # Build lookup from Gemini response
        gemini_map: Dict[str, Dict[str, Any]] = {}
        if isinstance(gemini_response, list):
            for item in gemini_response:
                if isinstance(item, dict) and "id" in item:
                    gemini_map[str(item["id"])] = item
        elif isinstance(gemini_response, dict):
            # Sometimes wrapped in {"articles": [...]}
            items = gemini_response.get("articles") or gemini_response.get("items") or []
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and "id" in item:
                        gemini_map[str(item["id"])] = item

        # Process each article in the batch
        for art in batch:
            art_id = str(art["id"])
            source_name = art.get("source", "")
            feed_default = get_feed_default_topic(source_name)
            raw_summary = art.get("summary", "")
            raw_title = art.get("title", "")

            final_topic = None
            final_summary = None
            final_tone = None

            # Check if Gemini provided valid result for this article
            item_res = gemini_map.get(art_id)
            if item_res:
                try:
                    final_topic = normalize_topic(item_res.get("topic"), feed_default)
                    final_summary = extract_two_sentences(item_res.get("ai_summary"))
                    final_tone = normalize_tone(item_res.get("tone"), "neutral")
                except Exception as parse_err:
                    logger.debug(f"Error parsing Gemini item for {art_id}: {parse_err}")

            # Fallback if Gemini failed or missed this item
            if not final_topic or not final_summary or not final_tone:
                fallback_count += 1
                final_topic = feed_default
                final_summary = extract_two_sentences(raw_summary or raw_title)
                final_tone = infer_fallback_tone(raw_title, raw_summary)

            # Update article record in Supabase
            try:
                client.table("articles").update({
                    "topic": final_topic,
                    "ai_summary": final_summary,
                    "tone": final_tone
                }).eq("id", art_id).execute()
                articles_scored += 1
            except Exception as up_err:
                logger.error(f"Failed to update article {art_id} in database: {up_err}")

        # Brief backoff between batches to preserve rate limits
        if i + batch_size < total_articles:
            time.sleep(0.5)

    logger.info(f"score_new_articles completed: {articles_scored} scored, {fallback_count} fallbacks.")
    return {
        "articles_scored": articles_scored,
        "batches_processed": batches_processed,
        "fallback_count": fallback_count
    }


# ---------------------------------------------------------------------------
# CLUSTER ARTICLES (LAST 48 HOURS)
# ---------------------------------------------------------------------------

def extract_title_keywords(title: str) -> Set[str]:
    """Extracts normalized content keywords from title for story clustering."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", title.lower())
    return set(w for w in words if w not in STOPWORDS)


def cluster_articles() -> Dict[str, Any]:
    """
    Groups articles about the same story from the last 48 hours using keyword
    overlap on titles, and assigns a shared cluster_id to each group.
    Saves cluster_id to the articles table.
    """
    client = get_supabase()
    cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=48)
    cutoff_iso = cutoff_dt.isoformat()

    # 1. Fetch articles from last 48 hours
    try:
        res = client.table("articles").select("id, title, published_at, cluster_id").gte("published_at", cutoff_iso).order("published_at", desc=True).execute()
        articles = res.data or []
    except Exception as e:
        logger.warning(f"Error fetching articles by published_at: {e}, falling back to recent articles")
        res = client.table("articles").select("id, title, published_at, cluster_id").order("created_at", desc=True).limit(150).execute()
        articles = res.data or []

    if len(articles) < 2:
        return {
            "articles_analyzed": len(articles),
            "clusters_formed": len(articles),
            "multi_article_clusters": 0
        }

    # 2. Extract keywords for each article
    article_keywords = [
        (art["id"], extract_title_keywords(art.get("title", "")))
        for art in articles
    ]

    n = len(articles)
    # Disjoint Set / Union-Find for clustering
    parent = list(range(n))

    def find(i: int) -> int:
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]

    def union(i: int, j: int):
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    # 3. Compare keyword overlap across titles
    for i in range(n):
        id_i, k_i = article_keywords[i]
        if not k_i:
            continue
        for j in range(i + 1, n):
            id_j, k_j = article_keywords[j]
            if not k_j:
                continue

            intersection = k_i & k_j
            overlap_count = len(intersection)
            union_count = len(k_i | k_j)

            # Two titles share a story if they share >= 3 keywords, or >= 2 keywords with Jaccard >= 0.3
            is_same_story = False
            if overlap_count >= 3:
                is_same_story = True
            elif overlap_count >= 2 and union_count > 0:
                similarity = overlap_count / union_count
                if similarity >= 0.30:
                    is_same_story = True

            if is_same_story:
                union(i, j)

    # 4. Group articles by root cluster
    cluster_groups: Dict[int, List[str]] = {}
    for i in range(n):
        root = find(i)
        cluster_groups.setdefault(root, []).append(articles[i]["id"])

    multi_article_clusters = 0
    updates: Dict[str, str] = {}

    for root, member_ids in cluster_groups.items():
        if len(member_ids) > 1:
            multi_article_clusters += 1
            # Generate deterministic shared cluster ID
            sorted_ids_str = "_".join(sorted(member_ids))
            shared_cid = f"cluster_{hashlib.md5(sorted_ids_str.encode()).hexdigest()[:12]}"
            for mid in member_ids:
                updates[mid] = shared_cid
        else:
            # Single article cluster
            single_id = member_ids[0]
            updates[single_id] = f"cluster_{single_id[:8]}"

    # 5. Save shared cluster_ids to articles table
    updated_count = 0
    for art_id, cid in updates.items():
        try:
            client.table("articles").update({"cluster_id": cid}).eq("id", art_id).execute()
            updated_count += 1
        except Exception as e:
            logger.debug(f"Error updating cluster_id for {art_id}: {e}")

    logger.info(f"cluster_articles finished: {len(articles)} analyzed, {len(cluster_groups)} clusters, {multi_article_clusters} multi-article stories.")
    return {
        "articles_analyzed": len(articles),
        "clusters_formed": len(cluster_groups),
        "multi_article_clusters": multi_article_clusters,
        "articles_updated": updated_count
    }


# ---------------------------------------------------------------------------
# PERSONALIZED SCORING (FOR NEWSPAPER EDITION RANKING)
# ---------------------------------------------------------------------------

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
        decay = 0.5 ** (hours_old / half_life_hours)
        return max(0.1, min(1.0, decay))
    except Exception:
        return 0.5


def score_article(
    article: Dict[str, Any],
    user_profile: Dict[str, Any],
    topic_weights: Dict[str, float]
) -> Dict[str, Any]:
    """Computes personalized relevance score for an article."""
    topic = (article.get("topic") or "World").lower().strip()
    tone = (article.get("tone") or "neutral").lower()

    topic_weight = topic_weights.get(topic, 1.0)
    user_interests = [i.lower() for i in (user_profile.get("interests") or [])]
    interest_bonus = 0.3 if topic in user_interests else 0.0

    recency_score = calculate_recency_score(article.get("published_at"))

    calm_mode = user_profile.get("calm_mode", False)
    calm_factor = 1.0
    if calm_mode:
        if tone == "heavy":
            calm_factor = 0.5
        elif tone in ("neutral", "light"):
            calm_factor = 1.2

    raw_score = (topic_weight + interest_bonus) * (0.6 * recency_score + 0.4) * calm_factor
    final_score = round(max(0.05, raw_score), 3)

    return {
        **article,
        "score": final_score,
        "score_breakdown": {
            "topic_weight": topic_weight,
            "interest_bonus": interest_bonus,
            "recency_score": round(recency_score, 3),
            "calm_factor": calm_factor,
        }
    }


def score_articles_for_user(articles: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
    """Scores and ranks candidate articles specifically for the specified user."""
    user = get_or_create_user(user_id)
    weights = get_topic_weights(user_id)

    scored_articles = [score_article(art, user, weights) for art in articles]
    scored_articles.sort(key=lambda x: x.get("score", 0), reverse=True)
    return scored_articles
