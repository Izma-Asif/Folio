import os
import re
import uuid
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Response, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("folio.main")

# Import Folio modules
from db import (
    DEFAULT_USER_ID,
    get_supabase,
    get_or_create_user,
    get_user,
    update_user_preferences,
    get_article,
    get_recent_articles,
    get_edition,
    get_latest_edition,
    list_user_editions,
    get_topic_weights,
    update_topic_weight,
    get_latest_editor_note,
)
from sources import (
    get_default_sources,
    get_sources_for_user,
    get_available_topics,
    add_custom_feed_for_user,
)
from fetcher import fetch_all, ingest_all_sources
from scorer import ALLOWED_TOPICS, score_new_articles, cluster_articles
from learner import record_interaction, get_user_learning_profile, decay
from angles import analyze_article_angles
from ranker import build_edition
from editor import apply_editor_instruction, list_user_editor_notes
from pdf_maker import generate_edition_pdf, render_edition_html
from ai import gemini_json

app = FastAPI(
    title="Folio API",
    description="Backend service for Folio: the personalized daily morning newspaper.",
    version="1.0.0"
)

# ---------------------------------------------------------------------------
# CORS CONFIGURATION
# Allows FRONTEND_URL and http://localhost:5173
# ---------------------------------------------------------------------------
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").strip()
allowed_origins = list(set([
    frontend_url,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# PYDANTIC SCHEMAS
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    interests: List[str] = Field(default_factory=list)
    custom_feeds: Optional[List[str]] = Field(default_factory=list)
    language: Optional[str] = "en"
    calm_mode: Optional[bool] = False
    visual_mode: Optional[str] = "broadsheet"


class UserPatch(BaseModel):
    interests: Optional[List[str]] = None
    custom_feeds: Optional[List[str]] = None
    language: Optional[str] = None
    calm_mode: Optional[bool] = None
    visual_mode: Optional[str] = None
    depth: Optional[str] = None
    length: Optional[str] = None
    topic: Optional[str] = None
    weight: Optional[float] = None
    topic_weights: Optional[Dict[str, float]] = None


class UserUpdate(BaseModel):
    interests: Optional[List[str]] = None
    custom_feeds: Optional[List[str]] = None
    language: Optional[str] = None
    calm_mode: Optional[bool] = None
    visual_mode: Optional[str] = None
    depth: Optional[str] = None
    length: Optional[str] = None


class InferInterestsRequest(BaseModel):
    text: str


class WeightUpdate(BaseModel):
    topic: str
    weight: float = Field(..., ge=0.1, le=5.0)


class InteractionEvent(BaseModel):
    user_id: Optional[str] = DEFAULT_USER_ID
    article_id: Optional[str] = None
    type: str = Field(..., pattern="^(click|save|skip)$")
    reason: Optional[str] = Field(
        default=None,
        description="Required context for skip: not_interested | already_know | too_negative"
    )


class GenerateEditionRequest(BaseModel):
    user_id: Optional[str] = DEFAULT_USER_ID
    edition_date: Optional[str] = None
    force_fetch: Optional[bool] = False


class CustomFeedRequest(BaseModel):
    feed_url: str


class EditorNoteRequest(BaseModel):
    text: str


# ---------------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health_check():
    """Health check endpoint required by the Folio specification."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# USERS & PREFERENCES
# ---------------------------------------------------------------------------

@app.post("/api/users")
def create_user_endpoint(req: UserCreate):
    """
    Creates a new user and sets topic_weights to 0.8 for chosen interests
    and 0.3 for all other topics. Returns {user_id}.
    """
    client = get_supabase()
    user_id = str(uuid.uuid4())

    user_record = {
        "id": user_id,
        "interests": req.interests,
        "custom_feeds": req.custom_feeds or [],
        "language": req.language or "en",
        "calm_mode": req.calm_mode if req.calm_mode is not None else False,
        "visual_mode": req.visual_mode or "broadsheet",
        "depth": "balanced",
        "length": "medium",
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        client.table("users").insert(user_record).execute()
    except Exception as e:
        logger.error(f"Error creating user in Supabase: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create user: {e}")

    # Set topic_weights to 0.8 for chosen interests and 0.3 for all other topics
    chosen_interests_lower = {i.lower().strip() for i in req.interests}
    for topic in ALLOWED_TOPICS:
        weight = 0.8 if topic.lower() in chosen_interests_lower else 0.3
        update_topic_weight(user_id, topic.lower(), weight)

    return {"user_id": user_id}


@app.get("/api/users/{user_id}/profile")
def get_user_profile_and_weights(user_id: str):
    """Returns user settings + topic weights."""
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    weights = get_topic_weights(user_id)
    profile = dict(user)
    profile["topic_weights"] = weights
    return profile


@app.patch("/api/users/{user_id}")
def patch_user(user_id: str, updates: UserPatch):
    """Updates user settings or sets a topic weight."""
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    payload = updates.model_dump(exclude_unset=True)

    # 1. Topic weight updates
    single_topic = payload.pop("topic", None)
    single_weight = payload.pop("weight", None)
    dict_weights = payload.pop("topic_weights", None)

    if single_topic and single_weight is not None:
        update_topic_weight(user_id, single_topic, float(single_weight))

    if dict_weights and isinstance(dict_weights, dict):
        for t, w in dict_weights.items():
            if w is not None:
                update_topic_weight(user_id, t, float(w))

    # 2. User settings updates
    valid_settings = {"interests", "custom_feeds", "language", "calm_mode", "visual_mode", "depth", "length"}
    settings_payload = {k: v for k, v in payload.items() if k in valid_settings and v is not None}
    if settings_payload:
        updated_user = update_user_preferences(user_id, settings_payload)
        if updated_user:
            user = updated_user

    weights = get_topic_weights(user_id)
    result = dict(user)
    result["topic_weights"] = weights
    return result


@app.get("/api/users/{user_id}")
def get_user_profile(user_id: str):
    """Retrieves user profile and newspaper reading settings."""
    user = get_user(user_id)
    if not user:
        user = get_or_create_user(user_id)
    return user


@app.put("/api/users/{user_id}")
def update_user_profile(user_id: str, updates: UserUpdate):
    """Updates user preferences (calm_mode, depth, length, visual_mode, etc.)."""
    payload = {k: v for k, v in updates.model_dump().items() if v is not None}
    updated = update_user_preferences(user_id, payload)
    if not updated:
        raise HTTPException(status_code=400, detail="Failed to update user preferences")
    return updated


@app.get("/api/users/{user_id}/weights")
def get_weights(user_id: str):
    """
    Returns topic weights sorted high → low, plus the last 10 interaction
    events enriched with their article titles for an activity list.
    """
    client = get_supabase()

    # Sorted weights
    raw_weights = get_topic_weights(user_id)
    sorted_weights = dict(
        sorted(raw_weights.items(), key=lambda x: x[1], reverse=True)
    )

    # Last 10 events with article title lookup
    try:
        evt_res = (
            client.table("events")
            .select("id, type, reason, article_id, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        events = evt_res.data or []
    except Exception:
        events = []

    # Batch-fetch article titles in one query
    article_ids = list({e["article_id"] for e in events if e.get("article_id")})
    title_map: Dict[str, str] = {}
    if article_ids:
        try:
            art_res = (
                client.table("articles")
                .select("id, title")
                .in_("id", article_ids)
                .execute()
            )
            for row in (art_res.data or []):
                title_map[str(row["id"])] = row.get("title", "")
        except Exception:
            pass

    activity = [
        {
            "id": e.get("id"),
            "type": e.get("type"),
            "reason": e.get("reason"),
            "article_id": e.get("article_id"),
            "article_title": title_map.get(str(e.get("article_id", "")), ""),
            "created_at": e.get("created_at"),
        }
        for e in events
    ]

    return {
        "user_id": user_id,
        "weights": sorted_weights,
        "activity": activity,
    }


@app.post("/api/users/{user_id}/weights")
def set_weight(user_id: str, req: WeightUpdate):
    """Sets a specific topic weight manually."""
    ok = update_topic_weight(user_id, req.topic, req.weight)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to update topic weight")
    return {"topic": req.topic, "weight": req.weight}


# ---------------------------------------------------------------------------
# INFER INTERESTS FROM TEXT & URLS
# ---------------------------------------------------------------------------

TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "Pakistan": ["pakistan", "urdu", "lahore", "karachi", "islamabad", "pakistani"],
    "World": ["world", "global", "international", "foreign", "geopolitics"],
    "Politics": ["politics", "political", "government", "parliament", "election", "policy", "minister"],
    "Business": ["business", "finance", "economy", "market", "startup", "stock", "trade", "investment"],
    "Tech": ["tech", "technology", "software", "hardware", "gadget", "cyber", "coding", "developer"],
    "AI": ["ai", "artificial intelligence", "machine learning", "llm", "openai", "deep learning", "neural"],
    "Sports": ["sports", "football", "soccer", "tennis", "olympics", "athletics", "basketball"],
    "Cricket": ["cricket", "babar", "kohli", "test match", "t20", "odi", "psl", "ipl", "pitch", "wicket"],
    "Science": ["science", "space", "nasa", "physics", "biology", "research", "scientific", "astronomy"],
    "Health": ["health", "medical", "medicine", "doctor", "wellness", "disease", "hospital", "pharma"],
    "Entertainment": ["entertainment", "movie", "film", "music", "cinema", "actor", "actress", "hollywood", "series", "tv"],
    "Culture": ["culture", "art", "history", "literature", "heritage", "museum", "cultural"],
    "Climate": ["climate", "environment", "carbon", "warming", "renewable", "pollution", "sustainability"]
}


def extract_urls_from_text(text: str) -> List[str]:
    """Finds all HTTP/HTTPS and www URLs in text."""
    url_pattern = r'(?:https?://|www\.)[^\s<>"\'\)]+'
    raw_urls = re.findall(url_pattern, text)
    cleaned = []
    for u in raw_urls:
        u = u.rstrip(".,;!?:")
        if u.startswith("www."):
            u = "https://" + u
        if u not in cleaned:
            cleaned.append(u)
    return cleaned


def fetch_url_metadata(url: str) -> Optional[Dict[str, str]]:
    """Fetches title and description for a URL with a 5-second timeout, ignoring failures."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Folio/1.0"
        }
        with httpx.Client(timeout=5.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return None
            html = resp.text

        soup = BeautifulSoup(html, "html.parser")
        title = ""
        og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "og:title"})
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()

        description = ""
        og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "og:description"}) or soup.find("meta", attrs={"name": "description"})
        if og_desc and og_desc.get("content"):
            description = og_desc["content"].strip()

        if title or description:
            return {"url": url, "title": title, "description": description}
        return None
    except Exception as e:
        logger.debug(f"Failed to fetch metadata for {url} (ignored): {e}")
        return None


def fallback_infer_interests(text: str, url_metadata: List[Dict[str, str]]) -> Dict[str, Any]:
    """Rule-based fallback interest inference when Gemini is unavailable."""
    combined = text.lower()
    for m in url_metadata:
        combined += " " + m.get("title", "").lower() + " " + m.get("description", "").lower()

    matched: List[str] = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if topic.lower() in combined or any(kw in combined for kw in keywords):
            matched.append(topic)

    if not matched:
        matched = ["World", "Tech"]

    style = "deep" if any(w in combined for w in ["deep", "in-depth", "long", "detailed", "analysis", "essay"]) else "short"

    if len(matched) == 1:
        top_str = matched[0]
    elif len(matched) == 2:
        top_str = f"{matched[0]} and {matched[1]}"
    else:
        top_str = f"{', '.join(matched[:-1])}, and {matched[-1]}"

    summary = f"You seem to like {top_str} news, in {style} reads."
    return {"topics": matched, "style": style, "summary": summary}


@app.post("/api/infer-interests")
def api_infer_interests(req: InferInterestsRequest):
    """
    Infers topics, reading depth style ('short' or 'deep'), and a summary sentence
    from free-form text and pasted article/channel URLs.
    """
    text = req.text.strip()
    if not text:
        return {
            "topics": ["World", "Tech"],
            "style": "short",
            "summary": "You seem to like World and Tech news, in short reads."
        }

    # Extract URLs and fetch metadata with 5s timeout, ignoring failures
    urls = extract_urls_from_text(text)
    url_metadata: List[Dict[str, str]] = []
    for u in urls[:5]:
        meta = fetch_url_metadata(u)
        if meta:
            url_metadata.append(meta)

    prompt = f"""You are an intelligent onboarding assistant for Folio, a bespoke morning newspaper.
The reader provided the following text about what they read (which may include article links, channel names, or topic preferences):
\"\"\"{text}\"\"\"

Webpage metadata fetched from links:
{json.dumps(url_metadata, indent=2) if url_metadata else "No link metadata"}

Allowed topics strictly limited to:
{ALLOWED_TOPICS}

Analyze their interests and reading depth. Return a JSON object with:
- "topics": list of topic strings chosen strictly from the allowed topics list above.
- "style": strictly "short" or "deep" ("short" for brief overviews, digests, or quick scans; "deep" for comprehensive deep-dives or investigative pieces).
- "summary": exactly one friendly sentence like 'You seem to like Pakistani business news and AI tools, in short reads.'

Return valid JSON with keys ["topics", "style", "summary"]."""

    res = gemini_json(prompt)
    if isinstance(res, dict) and "topics" in res:
        allowed_lower = {t.lower(): t for t in ALLOWED_TOPICS}
        matched_topics: List[str] = []
        raw_topics = res.get("topics", [])
        if isinstance(raw_topics, list):
            for rt in raw_topics:
                if isinstance(rt, str) and rt.lower().strip() in allowed_lower:
                    canonical = allowed_lower[rt.lower().strip()]
                    if canonical not in matched_topics:
                        matched_topics.append(canonical)

        style = res.get("style", "short").lower().strip()
        if style not in ("short", "deep"):
            style = "short"

        summary = res.get("summary")
        if not summary or not isinstance(summary, str):
            top_str = ", ".join(matched_topics) if matched_topics else "general news"
            summary = f"You seem to like {top_str}, in {style} reads."

        if matched_topics:
            return {
                "topics": matched_topics,
                "style": style,
                "summary": summary
            }

    # Fallback heuristic
    return fallback_infer_interests(text, url_metadata)


# ---------------------------------------------------------------------------
# SOURCES & FEEDS
# ---------------------------------------------------------------------------

@app.get("/api/sources")
def list_sources(topic: Optional[str] = None):
    """Lists available default curated RSS feeds and topics."""
    return {
        "topics": get_available_topics(),
        "sources": get_default_sources(topic)
    }


@app.get("/api/sources/user/{user_id}")
def list_user_sources(user_id: str):
    """Lists feeds active for the given user profile."""
    return get_sources_for_user(user_id)


@app.post("/api/sources/user/{user_id}/custom")
def add_custom_feed(user_id: str, req: CustomFeedRequest):
    """Adds a custom RSS feed URL to user's daily paper sources."""
    ok = add_custom_feed_for_user(user_id, req.feed_url)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to add custom feed")
    return {"status": "success", "feed_url": req.feed_url}


@app.post("/api/fetch")
def api_fetch():
    """
    Fetches articles across all 15 default RSS feeds and user custom_feeds.
    Returns the number of articles saved and the list of feeds that failed.
    """
    return fetch_all()


@app.post("/api/score")
def api_score():
    """
    Categorizes unscored articles in batches of 10 using Gemini (or fallback),
    and clusters articles from the last 48 hours sharing the same story.
    """
    scoring_res = score_new_articles()
    clustering_res = cluster_articles()
    return {
        "status": "success",
        "scoring": scoring_res,
        "clustering": clustering_res
    }


@app.post("/api/sources/fetch")
def trigger_fetch_sources(background_tasks: BackgroundTasks, max_per_source: int = Query(default=5, le=20)):
    """Triggers background ingestion of latest articles from RSS sources."""
    background_tasks.add_task(ingest_all_sources, max_per_source=max_per_source)
    return {"status": "ingestion_started", "max_per_source": max_per_source}


# ---------------------------------------------------------------------------
# ARTICLES & MULTI-PERSPECTIVE ANGLES
# ---------------------------------------------------------------------------

@app.get("/api/articles")
def list_articles(limit: int = Query(default=30, le=100), topic: Optional[str] = None):
    """Lists recent stored articles with optional topic filtering."""
    return get_recent_articles(limit=limit, topic=topic)


@app.get("/api/articles/{article_id}")
def get_article_detail(article_id: str):
    """Retrieves full details for a specific article."""
    art = get_article(article_id)
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
    return art


@app.get("/api/articles/{article_id}/angles")
def get_article_angles(article_id: str):
    """Generates a 360-degree multi-perspective editorial breakdown for an article."""
    art = get_article(article_id)
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
    return analyze_article_angles(art)


# ---------------------------------------------------------------------------
# EDITIONS & NEWSPAPER GENERATION
# ---------------------------------------------------------------------------

@app.post("/api/editions/generate")
def api_generate_edition(
    user_id: str = Query(default=DEFAULT_USER_ID),
    edition_date: Optional[str] = Query(default=None)
):
    """Builds (or replaces today's) personalized edition using ranker.build_edition and decays topic weights."""
    edition_content = build_edition(user_id=user_id, edition_date=edition_date)
    try:
        decay(user_id=user_id)
    except Exception as e:
        logger.warning(f"Failed to decay weights for user {user_id}: {e}")
    return edition_content


@app.get("/api/editions")
def api_list_editions(
    user_id: str = Query(default=DEFAULT_USER_ID),
    limit: int = Query(default=15, le=30)
):
    """Lists past editions for a user as summaries: {id, date, masthead, lead_title, story_count}."""
    client = get_supabase()
    try:
        res = (
            client.table("editions")
            .select("id, user_id, edition_date, content, created_at")
            .eq("user_id", user_id)
            .order("edition_date", desc=True)
            .limit(limit)
            .execute()
        )
        summaries = []
        for ed in (res.data or []):
            content = ed.get("content") or {}
            lead = content.get("lead") or {}
            all_articles = [lead] if lead else []
            for sec in content.get("sections", []):
                all_articles.extend(sec.get("articles", []))
            all_articles.extend(content.get("explore", []))
            summaries.append({
                "id": ed["id"],
                "date": ed.get("edition_date"),
                "masthead": content.get("masthead", "The Morning Folio"),
                "lead_title": lead.get("title", ""),
                "story_count": len(all_articles),
            })
        return summaries
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/editions/{edition_id}")
def api_get_edition(edition_id: str):
    """Retrieves a full edition by its ID."""
    client = get_supabase()
    try:
        res = client.table("editions").select("*").eq("id", edition_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Edition not found")
        ed = res.data[0]
        return ed.get("content") or ed
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/editions/{edition_id}/html")
def view_edition_html(edition_id: str):
    """Returns rendered publication HTML for viewing or browser printing."""
    edition = get_edition(edition_id)
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")
    html_content = render_edition_html(edition)
    return Response(content=html_content, media_type="text/html")


@app.get("/api/editions/{edition_id}/pdf")
def download_edition_pdf(edition_id: str):
    """Returns the edition compiled into an authentic newspaper broadsheet PDF."""
    edition = get_edition(edition_id)
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")

    pdf_bytes = generate_edition_pdf(edition)
    # Detect if response is PDF or fallback HTML
    if pdf_bytes.startswith(b"%PDF"):
        media_type = "application/pdf"
        filename = f"folio-edition-{edition.get('edition_date', 'today')}.pdf"
    else:
        media_type = "text/html"
        filename = f"folio-edition-{edition.get('edition_date', 'today')}.html"

    headers = {
        "Content-Disposition": f'inline; filename="{filename}"'
    }
    return Response(content=pdf_bytes, media_type=media_type, headers=headers)


# ---------------------------------------------------------------------------
# TELEMETRY & ONLINE LEARNING
# ---------------------------------------------------------------------------

@app.post("/api/events")
def post_event(event: InteractionEvent):
    """
    Logs a reader interaction and updates topic weights.

    Body: {user_id?, article_id?, type: 'click'|'save'|'skip', reason?}

    Weight deltas:
      click          +0.05
      save           +0.15
      skip + not_interested  -0.20
      skip + already_know    -0.05
      skip + too_negative    -0.10  (auto-enables calm_mode after 3× in 7 days)

    Weights clamped to [0.05, 1.0].
    """
    target_user_id = event.user_id or DEFAULT_USER_ID
    result = record_interaction(
        user_id=target_user_id,
        article_id=event.article_id,
        event_type=event.type,
        reason=event.reason,
    )
    return result


@app.get("/api/users/{user_id}/learning")
def get_learning_telemetry(user_id: str):
    """Returns user's learning profile, top affinity topics, and recent events."""
    return get_user_learning_profile(user_id)


# ---------------------------------------------------------------------------
# EDITOR NOTES
# ---------------------------------------------------------------------------

@app.get("/api/editor-notes/latest")
def get_latest_note(user_id: Optional[str] = Query(default=DEFAULT_USER_ID)):
    """Fetches the latest morning note from the AI Editor-in-Chief."""
    note = get_latest_editor_note(user_id)
    if not note:
        return {
            "summary": "Welcome to Folio",
            "note": "Welcome to Folio. Generate your first daily edition to receive your morning briefing.",
            "parsed": {}
        }
    return note


@app.post("/api/users/{user_id}/editor-note")
def post_user_editor_note(user_id: str, req: EditorNoteRequest):
    """
    Submits a plain-language instruction to the AI Editor-in-Chief.
    Applies topic adjustments and user settings updates, saves to editor_notes,
    and returns {summary, applied: parsed}.
    """
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text instruction cannot be empty")
    return apply_editor_instruction(user_id=user_id, text=req.text.strip())


@app.get("/api/users/{user_id}/editor-notes")
def get_user_editor_notes_list(user_id: str, limit: int = Query(default=20, le=50)):
    """Lists past editor notes for a user."""
    return list_user_editor_notes(user_id=user_id, limit=limit)
