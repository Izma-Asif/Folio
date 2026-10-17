import os
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger("folio.db")

try:
    from supabase import create_client, Client
except ImportError:
    create_client = None
    Client = Any

# Normalize Supabase URL in case dashboard URL was provided
def normalize_supabase_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    match = re.search(r"dashboard/project/([a-zA-Z0-9]+)", url)
    if match:
        project_ref = match.group(1)
        return f"https://{project_ref}.supabase.co"
    return url


SUPABASE_URL = normalize_supabase_url(os.getenv("SUPABASE_URL", ""))
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

_client: Optional[Client] = None


def get_supabase() -> Client:
    """Returns the singleton Supabase client, initializing it if necessary."""
    global _client
    if _client is not None:
        return _client

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be configured in environment or .env"
        )

    if create_client is None:
        raise ImportError(
            "supabase package is not installed. Install with 'pip install supabase'."
        )

    try:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return _client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        raise


# ---------------------------------------------------------------------------
# USERS TABLE HELPERS
# Schema: id, interests, custom_feeds, language, calm_mode, visual_mode, depth, length, created_at
# ---------------------------------------------------------------------------

DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"

def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetches user profile by user_id."""
    try:
        client = get_supabase()
        res = client.table("users").select("*").eq("id", user_id).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except Exception as e:
        logger.error(f"get_user failed for {user_id}: {e}")
        return None


def get_or_create_user(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Fetches existing user or creates a default personalized user."""
    target_id = user_id or DEFAULT_USER_ID
    existing = get_user(target_id)
    if existing:
        return existing

    new_user = {
        "id": target_id,
        "interests": ["tech", "ai", "science", "business", "world", "culture"],
        "custom_feeds": [],
        "language": "en",
        "calm_mode": False,
        "visual_mode": "broadsheet",
        "depth": "balanced",
        "length": "medium",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    try:
        client = get_supabase()
        res = client.table("users").insert(new_user).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return new_user
    except Exception as e:
        logger.warning(f"get_or_create_user insertion error: {e}")
        return new_user


def update_user_preferences(user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Updates user configuration fields."""
    try:
        client = get_supabase()
        res = client.table("users").update(updates).eq("id", user_id).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except Exception as e:
        logger.error(f"update_user_preferences failed for {user_id}: {e}")
        return None


# ---------------------------------------------------------------------------
# ARTICLES TABLE HELPERS
# Schema: id, title, link, source, summary, ai_summary, topic, image_url, tone, cluster_id, published_at, created_at
# ---------------------------------------------------------------------------

def upsert_article(article_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserts or updates an article based on link matching."""
    try:
        client = get_supabase()
        link = article_data.get("link")
        if not link:
            return None

        # Check existing article by link
        existing = client.table("articles").select("*").eq("link", link).execute()
        if existing.data and len(existing.data) > 0:
            art_id = existing.data[0]["id"]
            # Update missing fields if needed
            update_payload = {k: v for k, v in article_data.items() if v is not None and k != "id"}
            if update_payload:
                res = client.table("articles").update(update_payload).eq("id", art_id).execute()
                if res.data:
                    return res.data[0]
            return existing.data[0]

        if "id" not in article_data:
            article_data["id"] = str(uuid.uuid4())
        if "created_at" not in article_data:
            article_data["created_at"] = datetime.now(timezone.utc).isoformat()

        res = client.table("articles").insert(article_data).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except Exception as e:
        logger.error(f"upsert_article failed: {e}")
        return None


def get_article(article_id: str) -> Optional[Dict[str, Any]]:
    """Fetches a single article by ID."""
    try:
        client = get_supabase()
        res = client.table("articles").select("*").eq("id", article_id).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except Exception as e:
        logger.error(f"get_article failed: {e}")
        return None


def get_recent_articles(limit: int = 50, topic: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches recent articles ordered by published_at or created_at descending."""
    try:
        client = get_supabase()
        query = client.table("articles").select("*").order("created_at", desc=True).limit(limit)
        if topic:
            query = query.ilike("topic", f"%{topic}%")
        res = query.execute()
        return res.data or []
    except Exception as e:
        logger.error(f"get_recent_articles failed: {e}")
        return []


def get_articles_by_ids(article_ids: List[str]) -> List[Dict[str, Any]]:
    """Fetches list of articles by their UUIDs."""
    if not article_ids:
        return []
    try:
        client = get_supabase()
        res = client.table("articles").select("*").in_("id", article_ids).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"get_articles_by_ids failed: {e}")
        return []


# ---------------------------------------------------------------------------
# EDITIONS TABLE HELPERS
# Schema: id, user_id, edition_date, content, created_at
# ---------------------------------------------------------------------------

def save_edition(user_id: str, edition_date: str, content: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Saves a daily newspaper edition for a user."""
    try:
        client = get_supabase()
        # Check if an edition already exists for this date and user
        existing = client.table("editions").select("*").eq("user_id", user_id).eq("edition_date", edition_date).execute()
        if existing.data and len(existing.data) > 0:
            ed_id = existing.data[0]["id"]
            res = client.table("editions").update({"content": content}).eq("id", ed_id).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return existing.data[0]

        record = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "edition_date": edition_date,
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        res = client.table("editions").insert(record).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return record
    except Exception as e:
        logger.error(f"save_edition failed: {e}")
        return None


def get_edition(edition_id: str) -> Optional[Dict[str, Any]]:
    """Fetches an edition by ID."""
    try:
        client = get_supabase()
        res = client.table("editions").select("*").eq("id", edition_id).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except Exception as e:
        logger.error(f"get_edition failed: {e}")
        return None


def get_latest_edition(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetches the latest edition generated for a user."""
    try:
        client = get_supabase()
        res = client.table("editions").select("*").eq("user_id", user_id).order("edition_date", desc=True).limit(1).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except Exception as e:
        logger.error(f"get_latest_edition failed: {e}")
        return None


def list_user_editions(user_id: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Lists past editions for a user."""
    try:
        client = get_supabase()
        res = client.table("editions").select("id, user_id, edition_date, created_at").eq("user_id", user_id).order("edition_date", desc=True).limit(limit).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"list_user_editions failed: {e}")
        return []


# ---------------------------------------------------------------------------
# EVENTS TABLE HELPERS
# Schema: id, user_id, article_id, type, reason, created_at
# ---------------------------------------------------------------------------

def log_event(user_id: str, article_id: Optional[str], event_type: str, reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Logs an interaction event (read, dwell, thumbs_up, thumbs_down, bookmark, skip)."""
    try:
        client = get_supabase()
        record = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "article_id": article_id,
            "type": event_type,
            "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        res = client.table("events").insert(record).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return record
    except Exception as e:
        logger.error(f"log_event failed: {e}")
        return None


def get_user_events(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieves recent user events for learning and recommendation modeling."""
    try:
        client = get_supabase()
        res = client.table("events").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"get_user_events failed: {e}")
        return []


# ---------------------------------------------------------------------------
# TOPIC_WEIGHTS TABLE HELPERS
# Schema: user_id, topic, weight
# ---------------------------------------------------------------------------

def get_topic_weights(user_id: str) -> Dict[str, float]:
    """Returns mapping of topic -> weight (defaults to 1.0 if empty)."""
    try:
        client = get_supabase()
        res = client.table("topic_weights").select("topic, weight").eq("user_id", user_id).execute()
        weights: Dict[str, float] = {}
        if res.data:
            for item in res.data:
                topic = item.get("topic")
                weight = item.get("weight")
                if topic is not None and weight is not None:
                    weights[topic.lower()] = float(weight)
        return weights
    except Exception as e:
        logger.error(f"get_topic_weights failed: {e}")
        return {}


def update_topic_weight(user_id: str, topic: str, weight: float) -> bool:
    """Upserts a topic weight for a user."""
    try:
        client = get_supabase()
        clean_topic = topic.lower().strip()
        # Check existing
        existing = client.table("topic_weights").select("*").eq("user_id", user_id).eq("topic", clean_topic).execute()
        if existing.data and len(existing.data) > 0:
            client.table("topic_weights").update({"weight": weight}).eq("user_id", user_id).eq("topic", clean_topic).execute()
        else:
            client.table("topic_weights").insert({"user_id": user_id, "topic": clean_topic, "weight": weight}).execute()
        return True
    except Exception as e:
        logger.error(f"update_topic_weight failed: {e}")
        return False


def bulk_update_topic_weights(user_id: str, weights: Dict[str, float]) -> bool:
    """Updates multiple topic weights for a user."""
    success = True
    for topic, weight in weights.items():
        if not update_topic_weight(user_id, topic, weight):
            success = False
    return success


# ---------------------------------------------------------------------------
# EDITOR_NOTES TABLE HELPERS
# Schema: id, user_id, note, parsed, summary, created_at
# ---------------------------------------------------------------------------

def save_editor_note(user_id: str, note: str, parsed: Optional[Dict[str, Any]] = None, summary: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Saves an AI Editor-in-Chief note for the user."""
    try:
        client = get_supabase()
        record = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "note": note,
            "parsed": parsed or {},
            "summary": summary or "",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        res = client.table("editor_notes").insert(record).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return record
    except Exception as e:
        logger.error(f"save_editor_note failed: {e}")
        return None


def get_latest_editor_note(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetches the latest editor note for a user."""
    try:
        client = get_supabase()
        res = client.table("editor_notes").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except Exception as e:
        logger.error(f"get_latest_editor_note failed: {e}")
        return None
