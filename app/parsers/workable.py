"""Workable parser — extracts job listings from Workable-hosted job board HTML.

Workable boards render job cards starting with <div data-ui="job-summary">.
Each card contains nested divs, so we delimit cards by the start position of
the next card (or end of HTML) rather than matching a closing tag, which avoids
the lazy-quantifier truncation problem with nested divs.
"""
from __future__ import annotations

import re

from app.parsers import register_parser

_CARD_START_RE = re.compile(
    r'<div[^>]+data-ui=["\']job-summary["\']',
    re.IGNORECASE,
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
    starts = [m.start() for m in _CARD_START_RE.finditer(html)]
    if not starts:
        return []
    starts.append(len(html))
    jobs = []
    for i, start in enumerate(starts[:-1]):
        card = html[start:starts[i + 1]]
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
