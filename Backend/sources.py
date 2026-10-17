import logging
from typing import Any, Dict, List, Optional
from db import get_user, update_user_preferences

logger = logging.getLogger("folio.sources")

# Curated catalog of high-credibility default feeds
DEFAULT_SOURCES: List[Dict[str, Any]] = [
    # Tech & AI
    {
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "topic": "tech",
        "credibility": 0.95,
        "language": "en"
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "topic": "tech",
        "credibility": 0.90,
        "language": "en"
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "topic": "tech",
        "credibility": 0.88,
        "language": "en"
    },
    {
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
        "topic": "ai",
        "credibility": 0.96,
        "language": "en"
    },
    {
        "name": "Hacker News",
        "url": "https://news.ycombinator.com/rss",
        "topic": "tech",
        "credibility": 0.85,
        "language": "en"
    },
    # Science & Space
    {
        "name": "Quanta Magazine",
        "url": "https://api.quantamagazine.org/feed/",
        "topic": "science",
        "credibility": 0.98,
        "language": "en"
    },
    {
        "name": "ScienceDaily",
        "url": "https://www.sciencedaily.com/rss/all.xml",
        "topic": "science",
        "credibility": 0.92,
        "language": "en"
    },
    {
        "name": "NASA News",
        "url": "https://www.nasa.gov/news-release/feed/",
        "topic": "science",
        "credibility": 0.99,
        "language": "en"
    },
    # Business & Economics
    {
        "name": "The Economist",
        "url": "https://www.economist.com/the-world-this-week/rss.xml",
        "topic": "business",
        "credibility": 0.96,
        "language": "en"
    },
    {
        "name": "Financial Times",
        "url": "https://www.ft.com/rss/home",
        "topic": "business",
        "credibility": 0.97,
        "language": "en"
    },
    # World & Culture
    {
        "name": "BBC World News",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "topic": "world",
        "credibility": 0.94,
        "language": "en"
    },
    {
        "name": "NPR News",
        "url": "https://feeds.npr.org/1001/rss.xml",
        "topic": "world",
        "credibility": 0.93,
        "language": "en"
    },
    {
        "name": "The Atlantic",
        "url": "https://www.theatlantic.com/feed/all/",
        "topic": "culture",
        "credibility": 0.92,
        "language": "en"
    },
    # Design & Lifestyle
    {
        "name": "Dezeen",
        "url": "https://www.dezeen.com/feed/",
        "topic": "design",
        "credibility": 0.90,
        "language": "en"
    },
    {
        "name": "Smashing Magazine",
        "url": "https://www.smashingmagazine.com/feed/",
        "topic": "design",
        "credibility": 0.91,
        "language": "en"
    }
]

TOPICS: List[str] = ["tech", "ai", "science", "business", "world", "culture", "design"]


def get_available_topics() -> List[str]:
    """Returns list of supported high-level topic categories."""
    return TOPICS.copy()


def get_default_sources(topic: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns curated default RSS sources, optionally filtered by topic."""
    if not topic:
        return [dict(s) for s in DEFAULT_SOURCES]
    clean_topic = topic.lower().strip()
    return [dict(s) for s in DEFAULT_SOURCES if s.get("topic") == clean_topic]


def get_sources_for_user(user_id: str) -> List[Dict[str, Any]]:
    """
    Combines system curated sources with user custom feeds.
    Filters sources according to user's selected interests.
    """
    user = get_user(user_id)
    interests = (user.get("interests") or TOPICS) if user else TOPICS
    user_interests_set = set(t.lower() for t in interests)

    selected_sources = []
    for s in DEFAULT_SOURCES:
        if s["topic"] in user_interests_set or not user_interests_set:
            selected_sources.append(dict(s))

    # Add custom feeds defined by user
    if user and user.get("custom_feeds"):
        for custom_url in user["custom_feeds"]:
            selected_sources.append({
                "name": custom_url.split("/")[2] if "://" in custom_url else "Custom Feed",
                "url": custom_url,
                "topic": "custom",
                "credibility": 0.85,
                "language": user.get("language", "en")
            })

    return selected_sources


def add_custom_feed_for_user(user_id: str, feed_url: str) -> bool:
    """Appends a custom RSS feed URL to the user's profile."""
    user = get_user(user_id)
    if not user:
        return False
    feeds = list(user.get("custom_feeds") or [])
    clean_url = feed_url.strip()
    if clean_url not in feeds:
        feeds.append(clean_url)
        update_user_preferences(user_id, {"custom_feeds": feeds})
    return True


def remove_custom_feed_for_user(user_id: str, feed_url: str) -> bool:
    """Removes a custom RSS feed URL from the user's profile."""
    user = get_user(user_id)
    if not user:
        return False
    feeds = list(user.get("custom_feeds") or [])
    clean_url = feed_url.strip()
    if clean_url in feeds:
        feeds.remove(clean_url)
        update_user_preferences(user_id, {"custom_feeds": feeds})
    return True
