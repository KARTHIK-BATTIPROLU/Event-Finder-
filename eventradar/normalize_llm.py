"""
normalize_llm.py — Optional LLM-powered normalizer.

Only active when:
  1. An LLM API key is present (GEMINI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY).
  2. The caller explicitly passes use_llm=True (sources flag themselves as "messy HTML").

Priority: Gemini -> OpenAI -> Anthropic.

The LLM is asked to extract the schema fields from raw HTML/text and return JSON.
If the LLM call fails, returns the original event dict unchanged (graceful degradation).
"""
from __future__ import annotations

import json
import logging
import textwrap
from typing import Any

from eventradar import config

logger = logging.getLogger(__name__)

# ─── check availability ───────────────────────────────────────────────────────

def is_available() -> bool:
    return config.LLM_NORMALIZATION_ENABLED


def _active_backend() -> str | None:
    if config.GEMINI_API_KEY:
        return "gemini"
    if config.OPENAI_API_KEY:
        return "openai"
    if config.ANTHROPIC_API_KEY:
        return "anthropic"
    return None


# ─── prompt ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = textwrap.dedent("""\
    You are a data extraction assistant.  Extract event information from the given
    raw text or HTML and return ONLY a valid JSON object with these exact keys
    (omit keys you cannot find — do not guess):
      title, description, event_type, mode, city, venue,
      start_date, end_date, registration_deadline, prize_pool, organizer.
    
    Rules:
    - description: max 300 characters, plain text only
    - event_type: one of hackathon | meetup | conference | corporate_challenge | program | workshop
    - mode: one of online | offline | hybrid
    - dates: ISO YYYY-MM-DD if parseable
    - Return ONLY the JSON, no markdown fences, no explanation.
""")


def _make_user_message(raw_text: str) -> str:
    return f"Extract event data from:\n\n{raw_text[:4000]}"


# ─── backends ─────────────────────────────────────────────────────────────────

def _call_gemini(raw_text: str) -> dict[str, Any] | None:
    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = model.generate_content(
            [_SYSTEM_PROMPT, _make_user_message(raw_text)]
        )
        return json.loads(resp.text.strip())
    except Exception as exc:
        logger.warning("Gemini LLM call failed: %s", exc)
        return None


def _call_openai(raw_text: str) -> dict[str, Any] | None:
    try:
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _make_user_message(raw_text)},
            ],
            temperature=0,
            max_tokens=500,
        )
        return json.loads(resp.choices[0].message.content.strip())
    except Exception as exc:
        logger.warning("OpenAI LLM call failed: %s", exc)
        return None


def _call_anthropic(raw_text: str) -> dict[str, Any] | None:
    try:
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _make_user_message(raw_text)}],
        )
        return json.loads(msg.content[0].text.strip())
    except Exception as exc:
        logger.warning("Anthropic LLM call failed: %s", exc)
        return None


# ─── public interface ─────────────────────────────────────────────────────────

def normalize_with_llm(
    event: dict[str, Any],
    raw_text: str,
) -> dict[str, Any]:
    """
    Attempt LLM extraction from raw_text and merge into event dict.
    Falls back to returning event unchanged on any failure.
    """
    if not is_available():
        return event

    backend = _active_backend()
    extracted: dict[str, Any] | None = None

    if backend == "gemini":
        extracted = _call_gemini(raw_text)
    elif backend == "openai":
        extracted = _call_openai(raw_text)
    elif backend == "anthropic":
        extracted = _call_anthropic(raw_text)

    if not extracted or not isinstance(extracted, dict):
        return event

    # Merge: LLM fields fill gaps; don't overwrite fields already set
    for key, val in extracted.items():
        if val and not event.get(key):
            event[key] = val

    logger.debug("LLM normalization applied via %s", backend)
    return event
