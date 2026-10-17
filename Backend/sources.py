import logging
from typing import Any, Dict, List, Optional
from db import get_user, update_user_preferences

logger = logging.getLogger("folio.sources")

# 15 Curated RSS feeds across required categories
FEEDS: List[Dict[str, str]] = [
    # Pakistan (Dawn, Express Tribune, ProPakistani)
    {
        "name": "Dawn",
        "url": "https://www.dawn.com/feeds/home",
        "default_topic": "pakistan"
    },
    {
        "name": "Express Tribune",
        "url": "https://tribune.com.pk/feed/latest",
        "default_topic": "pakistan"
    },
    {
        "name": "ProPakistani",
        "url": "https://propakistani.pk/feed/",
        "default_topic": "pakistan"
    },

    # World (BBC World, Al Jazeera)
    {
        "name": "BBC World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "default_topic": "world"
    },
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "default_topic": "world"
    },

    # Business
    {
        "name": "BBC Business",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "default_topic": "business"
    },

    # Tech (TechCrunch, The Verge, Hacker News)
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "default_topic": "tech"
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "default_topic": "tech"
    },
    {
        "name": "Hacker News",
        "url": "https://news.ycombinator.com/rss",
        "default_topic": "tech"
    },

    # Sports (BBC Sport, ESPNcricinfo)
    {
        "name": "BBC Sport",
        "url": "https://feeds.bbci.co.uk/sport/rss.xml",
        "default_topic": "sports"
    },
    {
        "name": "ESPNcricinfo",
        "url": "https://www.espncricinfo.com/rss/content/story/feeds/0.xml",
        "default_topic": "sports"
    },

    # Science (NASA, Nature News)
    {
        "name": "NASA",
        "url": "https://www.nasa.gov/news-release/feed/",
        "default_topic": "science"
    },
    {
        "name": "Nature News",
        "url": "https://www.nature.com/nature.rss",
        "default_topic": "science"
    },

    # Health
    {
        "name": "BBC Health",
        "url": "https://feeds.bbci.co.uk/news/health/rss.xml",
        "default_topic": "health"
    },

    # Entertainment
    {
        "name": "BBC Entertainment",
        "url": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
        "default_topic": "entertainment"
    }
]

# Alias for compatibility with rest of codebase
DEFAULT_SOURCES = FEEDS
RSS_FEEDS = FEEDS

TOPICS: List[str] = [
    "pakistan",
    "world",
    "business",
    "tech",
    "sports",
    "science",
    "health",
    "entertainment"
]


def get_available_topics() -> List[str]:
    """Returns list of supported high-level topic categories."""
    return TOPICS.copy()


def get_default_sources(topic: Optional[str] = None) -> List[Dict[str, str]]:
    """Returns curated default RSS sources, optionally filtered by topic."""
    if not topic:
        return [dict(s) for s in FEEDS]
    clean_topic = topic.lower().strip()
    return [dict(s) for s in FEEDS if s.get("default_topic") == clean_topic]


def get_sources_for_user(user_id: str) -> List[Dict[str, Any]]:
    """
    Combines system curated sources with user custom feeds.
    Filters sources according to user's selected interests.
    """
    user = get_user(user_id)
    interests = (user.get("interests") or TOPICS) if user else TOPICS
    user_interests_set = set(t.lower() for t in interests)

    selected_sources = []
    for s in FEEDS:
        if s["default_topic"] in user_interests_set or not user_interests_set:
            selected_sources.append(dict(s))

    # Add custom feeds defined by user
    if user and user.get("custom_feeds"):
        for custom_url in user["custom_feeds"]:
            selected_sources.append({
                "name": custom_url.split("/")[2] if "://" in custom_url else "Custom Feed",
                "url": custom_url,
                "default_topic": "custom",
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
