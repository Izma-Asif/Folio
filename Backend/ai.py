import os
import re
import json
import time
import logging
from typing import Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

logger = logging.getLogger("folio.ai")

# Optional google-genai import
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    import httpx
except ImportError:
    httpx = None


def _clean_json_text(raw_text: str) -> str:
    """Strips markdown code fences, whitespace, and leading/trailing noise."""
    text = raw_text.strip()
    
    # Strip opening and closing code blocks e.g. ```json ... ``` or ``` ... ```
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    
    # Sometimes markdown wraps inside other markers
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if match:
        text = match.group(1).strip()
        
    return text


def _extract_and_parse_json(text: str) -> Any:
    """Parses JSON safely, attempting regex extraction if direct parse fails."""
    cleaned = _clean_json_text(text)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        # Fallback: extract the outermost JSON object {...} or array [...]
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
        if match:
            return json.loads(match.group(1))
        raise


def _call_gemini_api(prompt: str, api_key: str, model_name: str) -> str:
    """Executes a Gemini API request via google-genai SDK or httpx fallback."""
    # Ensure JSON instruction is clear in the prompt
    enhanced_prompt = (
        f"{prompt}\n\n"
        "IMPORTANT: Output valid JSON only. Do not wrap output in extra conversational text or commentary."
    )

    # 1. Try official google-genai SDK if available
    if genai is not None:
        try:
            client = genai.Client(api_key=api_key)
            config = None
            if types is not None and hasattr(types, "GenerateContentConfig"):
                config = types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            
            response = client.models.generate_content(
                model=model_name,
                contents=enhanced_prompt,
                config=config,
            )
            if response and getattr(response, "text", None):
                return response.text
        except Exception as sdk_err:
            logger.debug(f"google-genai SDK call failed, trying HTTP fallback: {sdk_err}")

    # 2. Resilient fallback using direct Google Generative Language REST API
    if httpx is not None:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        payload = {
            "contents": [
                {
                    "parts": [{"text": enhanced_prompt}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        headers = {
            "Content-Type": "application/json"
        }
        response = httpx.post(
            f"{url}?key={api_key}",
            json=payload,
            headers=headers,
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")

    raise RuntimeError("Neither google-genai SDK nor httpx could fulfill the request.")


def gemini_json(prompt: str) -> Optional[Any]:
    """
    Calls Gemini asking for JSON only, strips code fences, parses safely,
    retries once on failure, and returns None on failure (never raises).
    """
    try:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

        if not api_key:
            logger.warning("GEMINI_API_KEY is not set. gemini_json returning None.")
            return None

        # Attempt with 1 retry (total 2 attempts)
        for attempt in range(2):
            try:
                raw_response = _call_gemini_api(prompt, api_key, model)
                if not raw_response:
                    raise ValueError("Empty response received from Gemini.")
                
                parsed = _extract_and_parse_json(raw_response)
                return parsed
            except Exception as exc:
                logger.warning(f"gemini_json attempt {attempt + 1} failed: {exc}")
                if attempt == 0:
                    time.sleep(1.0)  # Brief backoff before single retry
                    continue
                return None
    except Exception as fatal_exc:
        logger.error(f"Unexpected error in gemini_json: {fatal_exc}")
        return None

    return None
