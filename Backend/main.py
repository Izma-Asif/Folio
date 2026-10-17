import os
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

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
from fetcher import ingest_all_sources
from learner import record_interaction, get_user_learning_profile
from angles import analyze_article_angles
from editor import generate_daily_edition
from pdf_maker import generate_edition_pdf, render_edition_html

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

class UserUpdate(BaseModel):
    interests: Optional[List[str]] = None
    custom_feeds: Optional[List[str]] = None
    language: Optional[str] = None
    calm_mode: Optional[bool] = None
    visual_mode: Optional[str] = None
    depth: Optional[str] = None
    length: Optional[str] = None


class WeightUpdate(BaseModel):
    topic: str
    weight: float = Field(..., ge=0.1, le=5.0)


class InteractionEvent(BaseModel):
    user_id: Optional[str] = DEFAULT_USER_ID
    article_id: Optional[str] = None
    event_type: str  # read, thumbs_up, thumbs_down, bookmark, skip
    reason: Optional[str] = None


class GenerateEditionRequest(BaseModel):
    user_id: Optional[str] = DEFAULT_USER_ID
    edition_date: Optional[str] = None
    force_fetch: Optional[bool] = False


class CustomFeedRequest(BaseModel):
    feed_url: str


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
    """Gets personalized topic weights for user."""
    return get_topic_weights(user_id)


@app.post("/api/users/{user_id}/weights")
def set_weight(user_id: str, req: WeightUpdate):
    """Sets a specific topic weight manually."""
    ok = update_topic_weight(user_id, req.topic, req.weight)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to update topic weight")
    return {"topic": req.topic, "weight": req.weight}


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


@app.post("/api/sources/fetch")
def trigger_fetch_sources(background_tasks: BackgroundTasks, max_per_source: int = Query(default=5, le=20)):
    """Triggers immediate ingestion of latest articles from RSS sources."""
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
def generate_edition(req: GenerateEditionRequest):
    """Orchestrates generation of the personalized daily edition."""
    target_user_id = req.user_id or DEFAULT_USER_ID
    edition = generate_daily_edition(
        user_id=target_user_id,
        edition_date=req.edition_date,
        force_fetch=req.force_fetch or False
    )
    return edition


@app.get("/api/editions/today")
def get_today_edition(user_id: Optional[str] = Query(default=DEFAULT_USER_ID)):
    """Fetches or automatically creates today's edition for the reader."""
    today_date = datetime.now().strftime("%Y-%m-%d")
    latest = get_latest_edition(user_id)

    if latest and latest.get("edition_date") == today_date:
        return latest

    # Generate fresh edition for today
    return generate_daily_edition(user_id=user_id, edition_date=today_date)


@app.get("/api/editions/{edition_id}")
def get_single_edition(edition_id: str):
    """Retrieves a specific edition by ID."""
    edition = get_edition(edition_id)
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")
    return edition


@app.get("/api/editions/user/{user_id}")
def list_editions(user_id: str, limit: int = Query(default=10, le=30)):
    """Lists past editions for user."""
    return list_user_editions(user_id=user_id, limit=limit)


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
    """Logs reader telemetry and updates personalized preference weights."""
    target_user_id = event.user_id or DEFAULT_USER_ID
    result = record_interaction(
        user_id=target_user_id,
        article_id=event.article_id,
        event_type=event.event_type,
        reason=event.reason
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
