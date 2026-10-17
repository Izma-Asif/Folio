import logging
from typing import Any, Dict, List, Optional, Union

from ai import gemini_json
from db import get_article

logger = logging.getLogger("folio.angles")


def generate_fallback_angles(title: str, summary: str, topic: str) -> Dict[str, Any]:
    """Generates structured heuristics when AI call is not reachable."""
    return {
        "title": title,
        "topic": topic,
        "core_thesis": summary[:200] if summary else title,
        "perspectives": [
            {
                "perspective_name": "Industry & Proponents",
                "viewpoint": "Advocates highlight progress, efficiency, and market expansion driven by these developments.",
                "sentiment": "optimistic"
            },
            {
                "perspective_name": "Critics & Skeptics",
                "viewpoint": "Emphasizes potential risks, oversight requirements, and unintended second-order consequences.",
                "sentiment": "cautious"
            },
            {
                "perspective_name": "Public Interest & Consumer",
                "viewpoint": "Focuses on everyday accessibility, privacy protections, and user costs.",
                "sentiment": "neutral"
            }
        ],
        "counter_arguments": [
            "Are long-term systemic costs understated compared to short-term gains?",
            "Whether regulatory and safety frameworks can keep pace with this trajectory."
        ],
        "what_it_means_for_you": f"As {topic.capitalize()} continues to evolve, stay aware of how this impacts workflow choices and market standards.",
        "unresolved_questions": [
            "What will be the primary milestone to measure success in the next 12 months?",
            "How will international competitors and regulatory bodies respond?"
        ]
    }


def analyze_article_angles(article_id_or_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Produces a multi-perspective editorial breakdown of an article,
    revealing conflicting viewpoints, counterarguments, and reader implications.
    """
    if isinstance(article_id_or_data, str):
        article = get_article(article_id_or_data)
        if not article:
            return {"error": "Article not found", "article_id": article_id_or_data}
    else:
        article = article_id_or_data

    title = article.get("title", "")
    summary = article.get("ai_summary") or article.get("summary") or ""
    topic = article.get("topic", "world")
    source = article.get("source", "News Source")

    prompt = f"""
You are the Chief Investigative Editor at Folio, a bespoke morning newspaper.
Provide a 360-degree multi-perspective "Angles" breakdown of this story:

Article Title: {title}
Source: {source}
Topic: {topic}
Summary: {summary}

Analyze the conflicting interests, underlying assumptions, and reader implications.
Return a JSON object with strictly these keys:
{{
  "title": "{title}",
  "core_thesis": "One concise paragraph explaining what happened and the central conflict or breakthrough",
  "perspectives": [
    {{
      "perspective_name": "Name of perspective or stakeholder group (e.g. Industry Innovators, Regulators, Consumer Advocates)",
      "viewpoint": "Their stance, priorities, and underlying motivations",
      "sentiment": "optimistic | critical | cautious | neutral"
    }}
  ],
  "counter_arguments": [
    "Key counter-argument or criticism against the dominant narrative"
  ],
  "what_it_means_for_you": "Direct, practical impact for the reader in their work or daily life",
  "unresolved_questions": [
    "Critical question 1 that remains unanswered",
    "Critical question 2 that will define what happens next"
  ]
}}
"""
    result = gemini_json(prompt)
    if isinstance(result, dict) and "perspectives" in result:
        result["article_id"] = article.get("id")
        return result

    # Fallback heuristic
    fallback = generate_fallback_angles(title, summary, topic)
    fallback["article_id"] = article.get("id")
    return fallback
