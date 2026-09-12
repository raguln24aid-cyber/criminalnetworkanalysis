import json
import logging
import re
from typing import Any, Dict, Optional

from groq import Groq

from app.config import get_settings
from app.services.groq_service import get_active_model, FALLBACK_MODELS, _is_rate_limit_error, _create_completion, _is_truncated_empty

settings = get_settings()
logger = logging.getLogger(__name__)

_client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None


def _parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def llm_json(system_prompt: str, user_content: str) -> Optional[Dict[str, Any]]:
    if not _client:
        return None

    active = get_active_model()
    candidates = [active] + [m for m in FALLBACK_MODELS if m != active]

    for model_to_use in candidates:
        try:
            completion = _create_completion(
                model_to_use,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_completion_tokens=2048,
                temperature=0.1,
            )
            if _is_truncated_empty(completion):
                # Same reasoning-model failure as the Copilot: the model spent
                # its whole budget on invisible internal reasoning and wrote
                # no JSON at all. Previously this fell through to
                # _parse_json("") -> None -> returned immediately, skipping
                # every other candidate model entirely.
                logger.warning(f"[LLM] {model_to_use} returned no content (reasoning used the full token budget), trying next model")
                continue
            text = completion.choices[0].message.content or ""
            parsed = _parse_json(text)
            if parsed is not None:
                return parsed
            logger.warning(f"[LLM] {model_to_use} response wasn't valid JSON, trying next model")
        except Exception as exc:
            if _is_rate_limit_error(exc):
                logger.warning(f"[LLM] {model_to_use} hit its rate/quota limit, trying next model")
                continue
            logger.error("[LLM] Request failed: %s", exc)
            return None

    logger.error("[LLM] All candidate models failed (rate-limited, empty, or unparsable)")
    return None
