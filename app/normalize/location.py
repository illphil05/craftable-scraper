"""Canonical location normalizer — Enhancement 6.

Two-pass normalizer:
  1. Regex + lookup table for well-known patterns (fast, no external calls).
  2. Structured output stored in city/state/country/location_type columns.

Geocoding fallback is intentionally omitted to keep the service dependency-free;
operators can add a geocoding step as a separate enrichment if needed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ── US state abbreviation / full-name map ─────────────────────────────────────

STATE_MAP: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    "PR": "Puerto Rico", "GU": "Guam", "VI": "Virgin Islands",
}

# Build reverse map: full name → abbreviation (case-insensitive lookup)
_FULL_TO_ABBR: dict[str, str] = {v.lower(): k for k, v in STATE_MAP.items()}

# ── Patterns ──────────────────────────────────────────────────────────────────

# Matches "Remote", "100% Remote", "Fully Remote", "Remote - US", "Remote (US)", etc.
_REMOTE_PATTERN = re.compile(
    r"\b(?:100\s*%\s*)?(?:fully\s+)?remote(?:\s*[-–—/|]\s*\w+)?\b",
    re.IGNORECASE,
)

# Matches "Hybrid", "Hybrid Remote", "Hybrid | Chicago"
_HYBRID_PATTERN = re.compile(r"\bhybrid\b", re.IGNORECASE)

# US "City, ST" or "City, State Full Name" (with optional ", USA" / ", US" suffix)
_US_CITY_STATE = re.compile(
    r"^(?P<city>[A-Za-z\s\-\.\']+?),?\s+"
    r"(?P<state_abbr>[A-Z]{2}|"
    + "|".join(re.escape(s) for s in _FULL_TO_ABBR)
    + r")"
    r"(?:\s*,?\s*(?:US|USA|United States))?\s*$",
    re.IGNORECASE,
)

# International: "City, Country" (fallback — just captures city + country)
_INTL_CITY_COUNTRY = re.compile(
    r"^(?P<city>[A-Za-z\s\-\.\']+?),\s+(?P<country>[A-Za-z\s]+)$"
)


@dataclass
class NormalizedLocation:
    city: str | None
    state: str | None
    country: str | None
    location_type: str  # "remote" | "hybrid" | "onsite" | "unknown"

    def as_dict(self) -> dict:
        return {
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "location_type": self.location_type,
        }


def normalize_location(raw: str | None) -> NormalizedLocation:
    """Return a NormalizedLocation from a raw location string.

    Returns a result with all None fields when raw is empty or
    completely unrecognised.
    """
    if not raw or not raw.strip():
        return NormalizedLocation(city=None, state=None, country=None, location_type="unknown")

    text = raw.strip()

    # Pass 1a: Remote detection (before hybrid so "Remote Hybrid" → remote)
    if _REMOTE_PATTERN.search(text):
        # Try to find a US city in the same string (e.g. "Remote – Chicago, IL")
        inner = _REMOTE_PATTERN.sub("", text).strip(" -–,|/")
        if m := _US_CITY_STATE.match(inner):
            city, state_abbr = _extract_city_state(m)
            return NormalizedLocation(city=city, state=state_abbr, country="US", location_type="remote")
        return NormalizedLocation(city=None, state=None, country=None, location_type="remote")

    # Pass 1b: Hybrid detection
    if _HYBRID_PATTERN.search(text):
        inner = _HYBRID_PATTERN.sub("", text).strip(" -–,|/")
        if m := _US_CITY_STATE.match(inner.strip()):
            city, state_abbr = _extract_city_state(m)
            return NormalizedLocation(city=city, state=state_abbr, country="US", location_type="hybrid")
        return NormalizedLocation(city=None, state=None, country=None, location_type="hybrid")

    # Pass 2: US city, state pattern
    if m := _US_CITY_STATE.match(text):
        city, state_abbr = _extract_city_state(m)
        return NormalizedLocation(city=city, state=state_abbr, country="US", location_type="onsite")

    # Pass 3: International city, country
    if m := _INTL_CITY_COUNTRY.match(text):
        city = m.group("city").strip().title()
        country = m.group("country").strip().title()
        # Exclude obvious noise
        if len(city) >= 2 and len(country) >= 2:
            return NormalizedLocation(city=city, state=None, country=country, location_type="onsite")

    return NormalizedLocation(city=None, state=None, country=None, location_type="unknown")


def _extract_city_state(m: re.Match) -> tuple[str, str]:
    """Return (city_title, state_abbr) from a _US_CITY_STATE match."""
    city = m.group("city").strip().title()
    raw_state = m.group("state_abbr").strip()
    if len(raw_state) == 2:
        state_abbr = raw_state.upper()
    else:
        state_abbr = _FULL_TO_ABBR.get(raw_state.lower(), raw_state.upper()[:2])
    return city, state_abbr
