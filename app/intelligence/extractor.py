"""Intelligence extraction: system detection (regex) and bullet extraction (LLM)."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

_TAXONOMY_PATH = Path(__file__).parent / "systems_taxonomy.json"
_systems_cache: list[str] | None = None

_LLM_MODEL = "claude-haiku-4-5-20251001"
_LLM_MAX_TOKENS = 1024
_MAX_TEXT_CHARS = 8000
_MAX_BULLETS = 50

_SYSTEM_PROMPT = (
    "You extract operations and finance signal phrases from hospitality job descriptions. "
    'Return ONLY a JSON array with objects {"category": "...", "bullet": "...", "confidence": "high|medium|low"}. '
    "Extract verbatim or near-verbatim phrases only — do not paraphrase. "
    "Categories: Cost Control, Financial Reporting, Budgeting & Forecasting, "
    "Data & Analytics, Compliance & Audit, Vendor Management. "
    "Only extract bullets relevant to these categories. If nothing relevant, return []."
)

# Module-level client singleton — created lazily once the API key is known.
_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _load_systems() -> list[str]:
    global _systems_cache
    if _systems_cache is None:
        with open(_TAXONOMY_PATH) as f:
            _systems_cache = json.load(f)["systems"]
    return _systems_cache


def detect_systems(text: str) -> list[str]:
    """Return deduped list of hospitality tech system names found in text."""
    if not text:
        return []
    systems = _load_systems()
    found: list[str] = []
    seen: set[str] = set()
    for name in systems:
        pattern = r"\b" + re.escape(name) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            key = name.lower()
            if key not in seen:
                seen.add(key)
                found.append(name)
    return found


async def extract_bullets(text: str) -> list[dict]:
    """Extract ops/finance bullet points using Claude Haiku via Anthropic SDK.

    Returns [] when ANTHROPIC_API_KEY is not set.
    Raises on API/network errors so callers can record enrichment failure.
    """
    if not os.environ.get("ANTHROPIC_API_KEY") or not text:
        return []

    client = _get_client()
    response = await client.messages.create(
        model=_LLM_MODEL,
        max_tokens=_LLM_MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": text[:_MAX_TEXT_CHARS]}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return []

    if not isinstance(result, list):
        return []

    # Validate shape and cap count
    valid = []
    for item in result:
        if isinstance(item, dict) and item.get("category") and item.get("bullet"):
            valid.append(item)
        if len(valid) >= _MAX_BULLETS:
            break
    return valid
