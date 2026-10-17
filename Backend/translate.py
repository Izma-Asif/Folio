import copy
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("folio.translate")
logger.setLevel(logging.INFO)

CHUNK_SIZE = 15  # articles per Gemini call
DEFAULT_MODEL = "gemini-2.5-flash"  # override with TRANSLATE_MODEL or GEMINI_MODEL in .env

# In-memory translation cache: edition_id -> translated edition dict
_TRANSLATION_CACHE: Dict[str, Dict[str, Any]] = {}


def _collect_articles(ed: Dict[str, Any]) -> List[Dict[str, Any]]:
    arts: List[Dict[str, Any]] = []
    if ed.get("lead"):
        arts.append(ed["lead"])
    for sec in ed.get("sections") or []:
        arts.extend(sec.get("articles") or [])
    arts.extend(ed.get("explore") or [])
    return arts


def _parse_json(text: str) -> Dict[str, Any]:
    text = (text or "").replace("```json", "").replace("```", "").strip()
    if not text:
        return {}
    data = json.loads(text)
    return data if isinstance(data, dict) else {}


def _call_gemini_json(prompt: str) -> Dict[str, Any]:
    """Calls Gemini and returns parsed JSON ({} on failure, reason is logged)."""
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("TRANSLATE_MODEL") or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL

    if not api_key:
        logger.warning("Urdu: GEMINI_API_KEY is missing from the environment (.env not loaded?)")
    else:
        try:
            from google import genai

            client = genai.Client(api_key=api_key)
            for attempt in range(3):
                try:
                    resp = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config={"response_mime_type": "application/json"},
                    )
                    return _parse_json(resp.text)
                except Exception as e:
                    msg = str(e)
                    if ("429" in msg or "RESOURCE_EXHAUSTED" in msg) and attempt < 2:
                        logger.warning(f"Urdu: rate limited, retrying in {10 * (attempt + 1)}s")
                        time.sleep(10 * (attempt + 1))
                        continue
                    raise
        except Exception as e:
            logger.warning(f"Urdu: direct Gemini call failed (model={model}): {e}")

    # fall back to the project's own helper
    try:
        from ai import gemini_json

        res = gemini_json(prompt)
        if isinstance(res, dict):
            return res
        logger.warning(f"Urdu: gemini_json returned {type(res).__name__}, expected dict")
    except Exception as e2:
        logger.warning(f"Urdu: gemini_json fallback failed: {e2}")
    return {}


def _prompt(payload: Dict[str, Any]) -> str:
    return (
        "Translate every string VALUE in the JSON below into natural, simple Urdu "
        "written in Urdu script, for a newspaper reader. Keep all keys and the "
        "structure EXACTLY the same. Do not change ids or keys. "
        "Return ONLY the JSON object.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def get_cached_translation(edition_id: str) -> Optional[Dict[str, Any]]:
    """Returns cached Urdu translation for an edition, or None."""
    return _TRANSLATION_CACHE.get(edition_id)


def translate_edition_to_urdu(ed: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Translates titles, summaries, 'why' lines, masthead, three_things and changes.
    Returns (edition_dict, success). On failure returns the original edition with success=False."""
    edition_id = str(ed.get("id", ""))
    logger.info("Urdu: translate_edition_to_urdu called")

    # Check in-memory cache first
    if edition_id:
        cached = _TRANSLATION_CACHE.get(edition_id)
        if cached:
            logger.info(f"Urdu: returning cached translation for edition {edition_id}")
            return cached, True

    # Deep-copy so we don't mutate the original English edition
    ed = copy.deepcopy(ed)
    try:
        arts = _collect_articles(ed)
        by_id = {str(a.get("id")): a for a in arts}
        ids = list(by_id)
        translated_count = 0
        logger.info(f"Urdu: found {len(ids)} articles to translate")

        for start in range(0, len(ids), CHUNK_SIZE):
            chunk = ids[start:start + CHUNK_SIZE]
            payload: Dict[str, Any] = {
                "articles": {
                    i: {
                        "title": by_id[i].get("title", ""),
                        "summary": by_id[i].get("summary", ""),
                        "why": by_id[i].get("why", ""),
                    }
                    for i in chunk
                }
            }
            if start == 0:
                payload["three_things"] = ed.get("three_things") or []
                payload["masthead"] = ed.get("masthead") or ""
                payload["changes"] = ed.get("changes") or []

            res = _call_gemini_json(_prompt(payload))
            if not res:
                logger.warning(f"Urdu: no translation for chunk starting at {start}")
                continue

            for aid, t in (res.get("articles") or {}).items():
                art = by_id.get(str(aid))
                if not art or not isinstance(t, dict):
                    continue
                art["title_en"] = art.get("title")
                art["summary_en"] = art.get("summary")
                art["title"] = t.get("title") or art.get("title")
                art["summary"] = t.get("summary") or art.get("summary")
                art["why"] = t.get("why") or art.get("why")
                translated_count += 1

            if start == 0:
                tt = res.get("three_things")
                if isinstance(tt, list) and tt:
                    ed["three_things"] = [str(x) for x in tt]
                m = res.get("masthead")
                if isinstance(m, str) and m.strip():
                    ed["masthead"] = m.strip()
                ch = res.get("changes")
                if isinstance(ch, list) and ch:
                    ed["changes"] = [str(x) for x in ch]

        logger.info(f"Urdu: translated {translated_count}/{len(ids)} articles")
        if translated_count:
            ed["language"] = "ur"
            if edition_id:
                _TRANSLATION_CACHE[edition_id] = ed
            return ed, True
        else:
            logger.warning("Urdu: no articles were translated")
            return ed, False
    except Exception as e:
        logger.warning(f"Urdu translation failed, keeping English: {e}")
        return ed, False