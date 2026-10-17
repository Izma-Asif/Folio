import re
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    import httpx
except ImportError:
    httpx = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from ai import gemini_json
from db import upsert_article
from sources import DEFAULT_SOURCES

logger = logging.getLogger("folio.fetcher")


def clean_html(raw_html: str) -> str:
    """Strips markup, scripts, and formats clean readable text."""
    if not raw_html:
        return ""
    if BeautifulSoup is None:
        # Fallback regex strip
        clean = re.sub(r"<[^>]+>", " ", raw_html)
        return " ".join(clean.split())

    try:
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "form"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        return " ".join(text.split())
    except Exception as e:
        logger.debug(f"clean_html error: {e}")
        return " ".join(raw_html.split())


def extract_image_url(entry: Any, raw_summary: str) -> Optional[str]:
    """Finds lead image from RSS enclosure, media_content, or HTML summary."""
    # 1. RSS Enclosures
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image/"):
                return enc.get("href")

    # 2. Media content (Yahoo Media RSS)
    if hasattr(entry, "media_content") and entry.media_content:
        for m in entry.media_content:
            if "url" in m:
                return m["url"]

    # 3. Media thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        for m in entry.media_thumbnail:
            if "url" in m:
                return m["url"]

    # 4. Extract from HTML body
    if BeautifulSoup and raw_summary:
        try:
            soup = BeautifulSoup(raw_summary, "html.parser")
            img = soup.find("img")
            if img and img.get("src"):
                src = img["src"]
                # Filter out tracking 1x1 pixels
                if not re.search(r"(1x1|pixel|spacer|feedburner|track)", src, re.IGNORECASE):
                    return src
        except Exception:
            pass

    return None


def generate_cluster_key(title: str) -> str:
    """Generates a normalized cluster ID for grouping identical or related breaking stories."""
    # Strip common noise and punctuation
    cleaned = re.sub(r"[^\w\s]", "", title.lower())
    words = [w for w in cleaned.split() if len(w) > 3][:6]
    key_phrase = " ".join(words)
    return hashlib.md5(key_phrase.encode("utf-8")).hexdigest()[:12]


def enrich_article_with_ai(title: str, summary: str, default_topic: str) -> Dict[str, Any]:
    """
    Uses gemini_json to synthesize an AI executive summary, classify topic,
    and determine tone. Falls back cleanly if AI is unavailable.
    """
    prompt = f"""
You are the lead editor for Folio, a personalized daily morning newspaper.
Analyze this news item:
Title: {title}
Summary: {summary}
Default Topic: {default_topic}

Return a JSON object with exactly these keys:
- "ai_summary": A crisp, high-signal 1-2 sentence executive briefing explaining what happened and why it matters.
- "topic": One of ["tech", "ai", "science", "business", "world", "culture", "design"].
- "tone": One of ["informative", "critical", "optimistic", "neutral", "urgent"].
"""
    result = gemini_json(prompt)
    if isinstance(result, dict) and "ai_summary" in result:
        return {
            "ai_summary": result.get("ai_summary", summary[:200]),
            "topic": result.get("topic", default_topic),
            "tone": result.get("tone", "neutral")
        }

    # Fallback heuristic
    return {
        "ai_summary": summary[:240] + ("..." if len(summary) > 240 else ""),
        "topic": default_topic,
        "tone": "informative"
    }


def parse_published_date(entry: Any) -> str:
    """Extracts published timestamp as an ISO-8601 string."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed_time = getattr(entry, attr, None)
        if parsed_time:
            try:
                dt = datetime(*parsed_time[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()


def fetch_source_feed(source: Dict[str, Any], max_items: int = 10) -> List[Dict[str, Any]]:
    """Fetches and parses a single RSS source."""
    if feedparser is None:
        logger.error("feedparser is not installed.")
        return []

    feed_url = source.get("url")
    source_name = source.get("name", "Unknown")
    default_topic = source.get("topic", "world")

    logger.info(f"Fetching RSS feed from: {source_name} ({feed_url})")

    try:
        # User-agent header is important for modern RSS endpoints
        headers = {
            "User-Agent": "FolioNewspaper/1.0 (+https://folio-paper.app; contact@folio.local)"
        }
        
        # Try fetching with httpx first to handle redirects and custom timeouts
        xml_content = None
        if httpx is not None:
            try:
                with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
                    resp = client.get(feed_url)
                    if resp.status_code == 200:
                        xml_content = resp.text
            except Exception as net_err:
                logger.debug(f"httpx fetch failed for {feed_url}: {net_err}, falling back to feedparser direct")

        if xml_content:
            parsed = feedparser.parse(xml_content)
        else:
            parsed = feedparser.parse(feed_url, request_headers=headers)

        articles = []
        for entry in parsed.entries[:max_items]:
            link = getattr(entry, "link", None)
            title = getattr(entry, "title", None)
            if not link or not title:
                continue

            raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            cleaned_summary = clean_html(raw_summary)
            image_url = extract_image_url(entry, raw_summary)
            published_at = parse_published_date(entry)
            cluster_id = generate_cluster_key(title)

            # AI enrichment (executive summary, tone, confirmed topic)
            enrichment = enrich_article_with_ai(title, cleaned_summary, default_topic)

            article_record = {
                "id": str(uuid.uuid4()),
                "title": title.strip(),
                "link": link.strip(),
                "source": source_name,
                "summary": cleaned_summary,
                "ai_summary": enrichment.get("ai_summary", cleaned_summary[:200]),
                "topic": enrichment.get("topic", default_topic),
                "image_url": image_url,
                "tone": enrichment.get("tone", "neutral"),
                "cluster_id": cluster_id,
                "published_at": published_at,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            articles.append(article_record)

        return articles

    except Exception as e:
        logger.error(f"Error fetching feed {feed_url}: {e}")
        return []


def ingest_all_sources(sources: Optional[List[Dict[str, Any]]] = None, max_per_source: int = 5) -> Dict[str, Any]:
    """
    Fetches articles across specified or default sources and upserts them into Supabase.
    Returns ingestion statistics.
    """
    target_sources = sources if sources is not None else DEFAULT_SOURCES
    total_fetched = 0
    total_saved = 0

    for src in target_sources:
        items = fetch_source_feed(src, max_items=max_per_source)
        total_fetched += len(items)
        for item in items:
            saved = upsert_article(item)
            if saved:
                total_saved += 1

    return {
        "sources_scanned": len(target_sources),
        "articles_fetched": total_fetched,
        "articles_saved_or_updated": total_saved
    }
