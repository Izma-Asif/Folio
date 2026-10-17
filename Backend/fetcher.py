import re
import email.utils
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import feedparser
import httpx
from bs4 import BeautifulSoup

from db import get_supabase
from sources import FEEDS

logger = logging.getLogger("folio.fetcher")


def strip_html(raw_html: str) -> str:
    """Strips all HTML tags and collapses whitespace to return clean plain text."""
    if not raw_html:
        return ""
    try:
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "form", "iframe"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        return " ".join(text.split())
    except Exception:
        clean = re.sub(r"<[^>]+>", " ", raw_html)
        return " ".join(clean.split())


def extract_image_url(entry: Any, raw_summary: str) -> Optional[str]:
    """
    Extracts lead image URL checking in order:
    1. media_content
    2. media_thumbnail
    3. enclosures
    4. First <img> tag in raw summary
    Returns None if no image is found.
    """
    # 1. media_content
    media_content = getattr(entry, "media_content", None) or entry.get("media_content")
    if media_content and isinstance(media_content, list):
        for item in media_content:
            if isinstance(item, dict) and item.get("url"):
                url = item["url"]
                medium = item.get("medium", "")
                mtype = item.get("type", "")
                if medium == "image" or mtype.startswith("image/") or not medium:
                    return url

    # 2. media_thumbnail
    media_thumbnail = getattr(entry, "media_thumbnail", None) or entry.get("media_thumbnail")
    if media_thumbnail and isinstance(media_thumbnail, list):
        for item in media_thumbnail:
            if isinstance(item, dict) and item.get("url"):
                return item["url"]

    # 3. enclosures
    enclosures = getattr(entry, "enclosures", None) or entry.get("enclosures")
    if enclosures and isinstance(enclosures, list):
        for enc in enclosures:
            if isinstance(enc, dict):
                href = enc.get("href")
                etype = enc.get("type", "")
                if href:
                    if etype.startswith("image/") or any(href.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
                        return href

    # 4. First <img> in the summary / content
    if raw_summary:
        try:
            soup = BeautifulSoup(raw_summary, "html.parser")
            img = soup.find("img")
            if img and img.get("src"):
                src = img["src"]
                # Skip tiny tracking pixels
                if not any(pixel in src.lower() for pixel in ["1x1", "pixel", "tracking", "spacer", "feedburner"]):
                    return src
        except Exception:
            pass

    # 5. If none, null
    return None


def parse_published_datetime(entry: Any) -> datetime:
    """Parses published date from entry into timezone-aware UTC datetime."""
    # Try published_parsed / updated_parsed struct_time
    for attr in ("published_parsed", "updated_parsed"):
        st = getattr(entry, attr, None)
        if st:
            try:
                return datetime(*st[:6], tzinfo=timezone.utc)
            except Exception:
                pass

    # Try raw string parsing
    for attr in ("published", "pubDate", "updated", "created"):
        val = getattr(entry, attr, None) or entry.get(attr)
        if val and isinstance(val, str):
            try:
                dt = email.utils.parsedate_to_datetime(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                return dt
            except Exception:
                try:
                    dt = datetime.fromisoformat(val)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)
                    return dt
                except Exception:
                    pass

    return datetime.now(timezone.utc)


def fetch_all() -> Dict[str, Any]:
    """
    Loops all RSS feeds and user custom_feeds with feedparser.
    Wraps each feed in try/except with a 10-second timeout so one dead feed never breaks the run.
    Extracts article metadata, skips articles older than 48 hours, and upserts
    into Supabase 'articles' using link as the unique key.
    
    Returns:
        Dict containing 'articles_saved' (int) and 'failed_feeds' (List[Dict[str, str]]).
    """
    client = get_supabase()

    # 1. Start with curated 15 feeds
    all_feeds: List[Dict[str, str]] = [dict(f) for f in FEEDS]
    seen_urls = set(f["url"].lower().strip() for f in FEEDS)

    # 2. Gather any custom feeds defined across users.custom_feeds
    try:
        users_resp = client.table("users").select("custom_feeds").execute()
        for u in (users_resp.data or []):
            custom_list = u.get("custom_feeds") or []
            for c_url in custom_list:
                if c_url and isinstance(c_url, str):
                    clean_c = c_url.strip()
                    if clean_c.lower() not in seen_urls:
                        seen_urls.add(clean_c.lower())
                        source_name = clean_c.split("/")[2] if "://" in clean_c else "Custom Feed"
                        all_feeds.append({
                            "name": source_name,
                            "url": clean_c,
                            "default_topic": "custom"
                        })
    except Exception as e:
        logger.warning(f"Could not load custom_feeds from users table: {e}")

    failed_feeds: List[Dict[str, str]] = []
    articles_saved = 0
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=48)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Folio/1.0",
        "Accept": "application/rss+xml, application/rdf+xml, application/atom+xml, application/xml, text/xml, */*"
    }

    # 3. Process feeds with 10-second timeout per feed
    for feed_info in all_feeds:
        feed_name = feed_info.get("name", "Unknown Feed")
        feed_url = feed_info.get("url", "").strip()
        default_topic = feed_info.get("default_topic", "world")

        if not feed_url:
            continue

        try:
            logger.info(f"Fetching RSS feed: {feed_name} ({feed_url})")
            
            # Fetch content with strict 10s timeout via httpx
            with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as http_client:
                resp = http_client.get(feed_url)
                resp.raise_for_status()
                feed_data = resp.content

            parsed = feedparser.parse(feed_data)

            # If entries empty and bozo flag raised without feed title, treat as failed feed
            if not parsed.entries and getattr(parsed, "bozo", 0) != 0 and not getattr(parsed, "feed", None):
                raise ValueError(f"Empty or unparseable XML feed from {feed_url}")

            # 4. Extract entries and upsert
            for entry in parsed.entries:
                link = getattr(entry, "link", None) or entry.get("link")
                title = getattr(entry, "title", None) or entry.get("title")

                if not link or not title:
                    continue

                link = str(link).strip()
                title = str(title).strip()

                # Published date check: Skip articles older than 48 hours
                pub_dt = parse_published_datetime(entry)
                if pub_dt < cutoff_time:
                    continue

                # Clean summary
                raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                text_summary = strip_html(raw_summary)

                # Extract image_url: media_content, media_thumbnail, enclosures, or <img>
                image_url = extract_image_url(entry, raw_summary)

                # Prepare article record matching Supabase articles table
                article_record = {
                    "title": title,
                    "link": link,
                    "source": feed_name,
                    "summary": text_summary,
                    "ai_summary": text_summary[:280] if text_summary else title,
                    "topic": default_topic,
                    "image_url": image_url,
                    "tone": "neutral",
                    "published_at": pub_dt.isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat()
                }

                # Upsert into Supabase articles using link as unique key
                try:
                    res = client.table("articles").upsert(article_record, on_conflict="link").execute()
                    if res.data:
                        articles_saved += 1
                except Exception as up_err:
                    logger.debug(f"Article upsert error for {link}: {up_err}")

        except Exception as exc:
            logger.warning(f"Feed failed: {feed_name} ({feed_url}) - {exc}")
            failed_feeds.append({
                "name": feed_name,
                "url": feed_url,
                "error": str(exc)
            })
            continue

    logger.info(f"fetch_all completed. Articles saved: {articles_saved}, Failed feeds: {len(failed_feeds)}")
    return {
        "articles_saved": articles_saved,
        "failed_feeds": failed_feeds
    }


# Backwards compatibility alias for other modules
def ingest_all_sources(sources: Optional[List[Dict[str, Any]]] = None, max_per_source: int = 5) -> Dict[str, Any]:
    """Compatibility wrapper calling fetch_all."""
    res = fetch_all()
    return {
        "articles_saved_or_updated": res.get("articles_saved", 0),
        "failed_feeds": res.get("failed_feeds", [])
    }
