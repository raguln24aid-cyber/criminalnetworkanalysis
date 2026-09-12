from groq import Groq
from app.config import get_settings
from app.prompts.copilot_prompt import COPILOT_SYSTEM_PROMPT
import logging

settings = get_settings()

client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
_active_model = None

def get_active_model():
    global _active_model
    if _active_model:
        return _active_model
        
    if not client:
        return settings.GROQ_MODEL
        
    try:
        models = client.models.list()
        available_models = [m.id for m in models.data]
        
        target_model = settings.GROQ_MODEL
        
        bad_words = ['guard', 'whisper', 'embed', 'vision', 'canopy', 'orpheus', 'tts', 'classifier', 'audio']
        
        def is_safe(m_name):
            m_lower = m_name.lower()
            return not any(bw in m_lower for bw in bad_words)

        if target_model in available_models and is_safe(target_model):
            _active_model = target_model
        else:
            # Groq's served model catalog changes over time (old Llama chat
            # models here have been retired in favor of these) - this list is
            # a priority order among whatever the account's /models actually
            # returns right now, not a guarantee any single one of these exists.
            preferred = [
                'openai/gpt-oss-20b',
                'openai/gpt-oss-120b',
                'qwen/qwen3.8-27b',
                'qwen/qwen3.6-27b',
                'llama-3.3-70b-versatile',
                'llama-3.1-8b-instant',
                'llama3-8b-8192',
                'llama3-70b-8192',
                'mixtral-8x7b-32768',
                'gemma2-9b-it',
                'allam-2-7b',
            ]
            for p in preferred:
                if p in available_models:
                    _active_model = p
                    break

            # Last resort: anything safe and not an agentic/tool-orchestration
            # model ("compound") that would return non-plain-text output the
            # JSON extraction and Copilot prompts don't expect.
            if not _active_model:
                safe_models = [m for m in available_models if is_safe(m) and 'compound' not in m.lower()]
                if safe_models:
                    _active_model = safe_models[0]
                elif [m for m in available_models if is_safe(m)]:
                    _active_model = [m for m in available_models if is_safe(m)][0]
                else:
                    _active_model = target_model
                
        print(f"Selected Groq Model: {_active_model}")
        return _active_model
    except Exception as e:
        print(f"Error fetching models: {e}")
        return settings.GROQ_MODEL

# Tried in order when the configured model hits its rate/quota limit. Each
# Groq model has its own separate token quota, so a 429 on one doesn't mean
# the others are exhausted too - this keeps the Copilot answering instead of
# surfacing a raw "Error code: 429" to the user (and stops one busy demo
# session from needing a manual model swap + restart mid-presentation).
FALLBACK_MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b", "qwen/qwen3.6-27b", "allam-2-7b"]


def _is_rate_limit_error(e: Exception) -> bool:
    msg = str(e)
    return "429" in msg or "rate_limit_exceeded" in msg


def _create_completion(model: str, messages: list, max_completion_tokens: int, temperature: float = 0.3):
    """Wraps chat.completions.create() with reasoning_effort handling.

    Reasoning models (the gpt-oss family, currently) spend part of their
    completion-token budget on an internal, invisible chain-of-thought
    before writing the visible answer. On a long/complex prompt that hidden
    reasoning can consume the ENTIRE token budget, leaving finish_reason
    "length" and an empty message.content - a 200 OK response with nothing
    in it, which is what was silently reaching the Copilot UI as a blank
    reply. reasoning_effort="low" caps how much of the budget reasoning is
    allowed to eat, but not every model accepts that parameter (plain chat
    models 400 on it) - so try it first and drop it only if the model
    itself rejects it, rather than hardcoding which models "are" reasoning
    models (Groq's lineup changes)."""
    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
        top_p=1,
        stream=False,
        stop=None,
    )
    try:
        return client.chat.completions.create(reasoning_effort="low", **kwargs)
    except Exception as e:
        if "reasoning_effort" in str(e):
            return client.chat.completions.create(**kwargs)
        raise


def _is_truncated_empty(completion) -> bool:
    """True when the model hit its token limit having produced no usable
    answer - the specific reasoning-model failure mode above. Retrying the
    same request against this model would just reproduce it, so callers
    should treat this like a rate limit and move to the next candidate."""
    choice = completion.choices[0]
    return not (choice.message.content or "").strip() and choice.finish_reason == "length"


def query_copilot(query: str, context: str = ""):
    if not client:
        # No API key configured - be honest about that instead of inventing
        # an investigative claim about people/accounts that may not even
        # exist in the actual case data.
        return {
            "answer": "The Copilot's LLM is not configured (no GROQ_API_KEY set), so I can't answer questions right now. Set GROQ_API_KEY in the backend .env and restart the server.",
            "evidence": [],
            "confidence": 0,
            "uncertainty": "LLM unavailable.",
            "recommended_verification": "Configure GROQ_API_KEY."
        }

    system_prompt = COPILOT_SYSTEM_PROMPT
    candidates = [get_active_model()] + [m for m in FALLBACK_MODELS if m != get_active_model()]

    last_error = None
    for model_to_use in candidates:
        try:
            completion = _create_completion(
                model_to_use,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"CASE DATA:\n{context}\n\nINVESTIGATOR QUESTION: {query}"}
                ],
                max_completion_tokens=3000,
            )
            if _is_truncated_empty(completion):
                logging.warning(f"[COPILOT] {model_to_use} used its whole token budget on internal reasoning "
                                 f"and returned no answer text, trying next model")
                last_error = RuntimeError(f"{model_to_use} returned an empty response (token budget exhausted by reasoning)")
                continue
            text_response = completion.choices[0].message.content
            return {
                "answer": text_response,
                "evidence": ["Extracted from context"],
                "confidence": 0.90,
                "uncertainty": "LLM generated response",
                "recommended_verification": "Human review required"
            }
        except Exception as e:
            last_error = e
            if _is_rate_limit_error(e):
                logging.warning(f"[COPILOT] {model_to_use} hit its rate/quota limit, trying next model")
                continue
            break  # non-rate-limit error (bad key, network, etc.) - retrying other models won't help

    return {
        "answer": (
            "The Copilot's language model couldn't produce an answer for this question - it ran out of its "
            "response budget before finishing (this can happen on very broad questions against a large graph). "
            "Try asking about a more specific entity, or narrowing the question, and try again."
            if isinstance(last_error, RuntimeError) and "empty response" in str(last_error)
            else f"Error querying Groq: {str(last_error)}"
        ),
        "evidence": [],
        "confidence": 0,
        "uncertainty": "Error",
        "recommended_verification": "Check API key and connectivity." if not isinstance(last_error, RuntimeError) else "Rephrase the question and retry.",
    }
