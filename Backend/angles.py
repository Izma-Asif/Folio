"""
angles.py – Multi-source perspective and emphasis extraction for Folio.

For each cluster of articles with 2 or more distinct sources inside an edition,
calls Gemini once (batching all multi-source clusters in a single API call)
with each source's title and summary.

For each cluster, returns per source one neutral short phrase describing what that
source emphasizes, e.g.:
    {"source": "Dawn", "focus": "the budget numbers"}

Rules:
- Do not judge accuracy.
- Do not label any source biased.
- Describe emphasis only.
- Skip silently if Gemini fails.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

from ai import gemini_json
from db import get_article

logger = logging.getLogger("folio.angles")


def extract_cluster_angles(
    clusters: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, List[Dict[str, str]]]:
    """
    Takes a dictionary mapping cluster_id -> list of article dicts in that cluster.
    Filters for clusters with 2 or more distinct sources.
    Batches all such clusters into a single Gemini prompt.

    Returns a dict mapping cluster_id -> list of {"source": str, "focus": str}.
    If Gemini fails or returns malformed output, returns an empty dict (skips silently).
    """
    # 1. Filter for clusters with 2 or more distinct sources
    valid_clusters: Dict[str, List[Dict[str, Any]]] = {}
    for cid, members in clusters.items():
        distinct_sources = list(dict.fromkeys(
            (m.get("source") or "").strip()
            for m in members
            if (m.get("source") or "").strip()
        ))
        if len(distinct_sources) >= 2:
            valid_clusters[str(cid)] = members

    if not valid_clusters:
        return {}

    # 2. Build structured text representation of all clusters
    cluster_blocks: List[str] = []
    for idx, (cid, members) in enumerate(valid_clusters.items(), start=1):
        # Deduplicate members by source to present one representative headline/summary per source
        seen_sources = set()
        source_lines: List[str] = []
        for m in members:
            src = (m.get("source") or "Unknown").strip()
            if src in seen_sources:
                continue
            seen_sources.add(src)
            title = (m.get("title") or "").strip()
            summary = (m.get("ai_summary") or m.get("summary") or "")[:200].strip()
            source_lines.append(f'  - Source: "{src}" | Headline: "{title}" | Summary: "{summary}"')

        block = f'Cluster ID "{cid}":\n' + "\n".join(source_lines)
        cluster_blocks.append(block)

    prompt = f"""You are an objective media analysis engine.
Below are news story clusters where multiple news sources reported on the same overarching topic or event.

For each cluster, analyze what each reporting source chooses to emphasize.
For every source in each cluster, write ONE neutral, factual, short phrase describing what that specific source emphasizes (e.g. "the budget numbers", "eyewitness accounts", "diplomatic reactions", "economic implications").

STRICT GUIDELINES:
1. Do NOT judge accuracy or factuality.
2. Do NOT label any source as biased, partisan, unreliable, or slanted.
3. Describe emphasis ONLY.
4. Keep each focus phrase short (3 to 8 words).

Clusters to analyze:
{chr(10).join(cluster_blocks)}

Return ONLY a valid JSON object mapping each cluster ID string to an array of objects with "source" and "focus" keys.
Example format:
{{
  "cluster_id_1": [
    {{"source": "Dawn", "focus": "the budget numbers and deficit"}},
    {{"source": "Express Tribune", "focus": "parliamentary debate reactions"}}
  ]
}}
"""

    try:
        res = gemini_json(prompt)
        if not isinstance(res, dict):
            logger.debug("extract_cluster_angles: Gemini returned non-dict response")
            return {}

        results: Dict[str, List[Dict[str, str]]] = {}
        for cid, angle_list in res.items():
            cid_str = str(cid)
            if not isinstance(angle_list, list):
                continue
            cleaned_angles: List[Dict[str, str]] = []
            for item in angle_list:
                if isinstance(item, dict) and "source" in item and "focus" in item:
                    cleaned_angles.append({
                        "source": str(item["source"]).strip(),
                        "focus": str(item["focus"]).strip()
                    })
            if cleaned_angles:
                results[cid_str] = cleaned_angles

        return results
    except Exception as e:
        logger.debug(f"extract_cluster_angles failed silently: {e}")
        return {}


# ---------------------------------------------------------------------------
# Single-article 360-degree breakdown (preserved for GET /api/articles/{id}/angles)
# ---------------------------------------------------------------------------

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
    Produces a 360-degree multi-perspective breakdown of an individual article.
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

    fallback = generate_fallback_angles(title, summary, topic)
    fallback["article_id"] = article.get("id")
    return fallback
