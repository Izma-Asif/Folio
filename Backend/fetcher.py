import re
import email.utils
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

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


def fetch_article_meta_image(url: str) -> Optional[str]:
    """
    Fetches the article page with httpx (5-second timeout, browser-like User-Agent,
    following redirects) and reads the og:image or twitter:image meta tag.
    Ignores failures and returns None if unfound.
    """
    if not url or not url.startswith("http"):
        return None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Folio/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }
        with httpx.Client(timeout=5.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return None
            html = resp.text

        soup = BeautifulSoup(html, "html.parser")
        # Try og:image and twitter:image variants
        meta_tags = [
            soup.find("meta", property="og:image"),
            soup.find("meta", attrs={"name": "og:image"}),
            soup.find("meta", property="twitter:image"),
            soup.find("meta", attrs={"name": "twitter:image"}),
            soup.find("meta", property="twitter:image:src"),
            soup.find("meta", attrs={"name": "twitter:image:src"})
        ]
        for tag in meta_tags:
            if tag and tag.get("content"):
                src = tag["content"].strip()
                if src.startswith("http://") or src.startswith("https://"):
                    return src
        return None
    except Exception as e:
        logger.debug(f"fetch_article_meta_image failed for {url}: {e}")
        return None


def backfill_missing_images(limit: int = 60) -> int:
    """
    Concurrently finds up to `limit` newest articles in the articles table
    missing an image_url, scrapes og:image / twitter:image meta tags,
    ignores failures, and saves results to the articles table.
    """
    client = get_supabase()
    try:
        # Fetch newest articles without image_url
        res = (
            client.table("articles")
            .select("id, link, image_url")
            .order("created_at", desc=True)
            .limit(limit * 3)
            .execute()
        )
        candidates = [
            a for a in (res.data or [])
            if not a.get("image_url") and a.get("link")
        ][:limit]
    except Exception as e:
        logger.warning(f"Error querying articles for image backfill: {e}")
        return 0

    if not candidates:
        logger.info("backfill_missing_images: no articles missing image_url found.")
        return 0

    updated_count = 0

    def process_article(art: Dict[str, Any]) -> Optional[Tuple[str, str]]:
        art_id = art["id"]
        link = art["link"]
        img = fetch_article_meta_image(link)
        if img:
            return (art_id, img)
        return None

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_article, art) for art in candidates]
        for fut in as_completed(futures):
            try:
                result = fut.result()
                if result:
                    art_id, img_url = result
                    client.table("articles").update({"image_url": img_url}).eq("id", art_id).execute()
                    updated_count += 1
            except Exception as up_err:
                logger.debug(f"Failed updating article image: {up_err}")

    logger.info(f"backfill_missing_images completed: found & updated {updated_count}/{len(candidates)} article images.")
    return updated_count


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

    def fetch_single_feed(feed_info: Dict[str, str]) -> Dict[str, Any]:
        name = feed_info.get("name", "Unknown Feed")
        url = feed_info.get("url", "").strip()
        if not url:
            return {"name": name, "url": url, "articles": [], "error": None}

        try:
            with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as http_client:
                resp = http_client.get(url)
                resp.raise_for_status()
                feed_data = resp.content

            parsed = feedparser.parse(feed_data)
            if not parsed.entries and getattr(parsed, "bozo", 0) != 0 and not getattr(parsed, "feed", None):
                return {"name": name, "url": url, "articles": [], "error": f"Empty or unparseable XML feed from {url}"}

            articles = []
            for entry in parsed.entries:
                link = getattr(entry, "link", None) or entry.get("link")
                title = getattr(entry, "title", None) or entry.get("title")
                if not link or not title:
                    continue

                pub_dt = parse_published_datetime(entry)
                if pub_dt < cutoff_time:
                    continue

                raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                text_summary = strip_html(raw_summary)
                image_url = extract_image_url(entry, raw_summary)

                articles.append({
                    "title": str(title).strip(),
                    "link": str(link).strip(),
                    "source": name,
                    "summary": text_summary,
                    "ai_summary": None,
                    "topic": None,
                    "image_url": image_url,
                    "tone": "neutral",
                    "published_at": pub_dt.isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat()
                })

            return {"name": name, "url": url, "articles": articles, "error": None}
        except Exception as exc:
            return {"name": name, "url": url, "articles": [], "error": str(exc)}

    # Fetch all feeds concurrently
    all_articles_to_save: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_single_feed, f) for f in all_feeds]
        for fut in as_completed(futures):
            res = fut.result()
            if res["error"]:
                logger.warning(f"Feed failed: {res['name']} ({res['url']}) - {res['error']}")
                failed_feeds.append({
                    "name": res["name"],
                    "url": res["url"],
                    "error": res["error"]
                })
            else:
                all_articles_to_save.extend(res["articles"])

    # Batch upsert articles in chunks of 50
    chunk_size = 50
    for i in range(0, len(all_articles_to_save), chunk_size):
        chunk = all_articles_to_save[i:i + chunk_size]
        try:
            res = client.table("articles").upsert(chunk, on_conflict="link").execute()
            if res.data:
                articles_saved += len(res.data)
        except Exception as up_err:
            logger.debug(f"Batch article upsert error: {up_err}")

    # Run image backfill for missing images
    try:
        backfilled = backfill_missing_images(limit=60)
        logger.info(f"fetch_all image backfill updated {backfilled} articles.")
    except Exception as bf_err:
        logger.warning(f"Error running image backfill at end of fetch_all: {bf_err}")

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
