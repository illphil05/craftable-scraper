"""Workable parser — extracts job listings from Workable-hosted job board HTML.

Workable boards render job cards as <div data-ui="job-summary"> containing a
title (h2/h3.job-title), location span, and apply link. Parsing per-card
prevents location spans from navigation/filter elements from corrupting pairing.
"""
from __future__ import annotations

import re

from app.parsers import register_parser

_CARD_RE = re.compile(
    r'<div[^>]+data-ui=["\']job-summary["\'][^>]*>(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)
_TITLE_RE = re.compile(
    r'<(?:h2|h3)[^>]*class="[^"]*job-title[^"]*"[^>]*>(.*?)</(?:h2|h3)>',
    re.DOTALL | re.IGNORECASE,
)
_LOC_RE = re.compile(
    r'<span[^>]*class="[^"]*location[^"]*"[^>]*>(.*?)</span>',
    re.DOTALL | re.IGNORECASE,
)
_URL_RE = re.compile(
    r'href="(https://apply\.workable\.com/[^"]+)"',
    re.IGNORECASE,
)
_TEXT_RE = re.compile(r'<[^>]+>')


@register_parser("apply.workable.com", [])
def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    """Extract job listings from a Workable job board page."""
    jobs = []
    for card_m in _CARD_RE.finditer(html):
        card = card_m.group(1)
        title_m = _TITLE_RE.search(card)
        if not title_m:
            continue
        title = _TEXT_RE.sub("", title_m.group(1)).strip()
        if not title:
            continue
        loc_m = _LOC_RE.search(card)
        location = (_TEXT_RE.sub("", loc_m.group(1)).strip() or None) if loc_m else None
        url_m = _URL_RE.search(card)
        job_url = url_m.group(1) if url_m else url
        jobs.append({
            "title": title,
            "company_name": company_name or "",
            "url": job_url,
            "location": location,
            "snippet": None,
            "description": None,
            "department": None,
        })
    return jobs
