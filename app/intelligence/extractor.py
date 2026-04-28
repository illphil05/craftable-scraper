"""Intelligence extraction: system detection (regex) and bullet extraction (LLM)."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

_TAXONOMY_PATH = Path(__file__).parent / "systems_taxonomy.json"
_systems_cache: list[str] | None = None


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
        pattern = re.escape(name)
        if re.search(pattern, text, re.IGNORECASE):
            key = name.lower()
            if key not in seen:
                seen.add(key)
                found.append(name)
    return found


_SYSTEM_PROMPT = (
    "You extract operations and finance signal phrases from hospitality job descriptions. "
    'Return ONLY a JSON array with objects {"category": "...", "bullet": "...", "confidence": "high|medium|low"}. '
    "Extract verbatim or near-verbatim phrases only — do not paraphrase. "
    "Categories: Cost Control, Financial Reporting, Budgeting & Forecasting, "
    "Data & Analytics, Compliance & Audit, Vendor Management. "
    "Only extract bullets relevant to these categories. If nothing relevant, return []."
)


async def extract_bullets(text: str) -> list[dict]:
    """Extract ops/finance bullet points using Claude Haiku via Anthropic SDK.

    Returns [] if ANTHROPIC_API_KEY is not set or on any parse error.
    Only calls the LLM when the env var is present.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not text:
        return []

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": text[:8000]}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        return json.loads(raw)
    except Exception:
        return []
