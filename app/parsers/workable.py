"""Workable parser — extracts job listings from Workable-hosted job board HTML.

Workable boards render job cards with [data-ui="job-summary"] or class="whr-item"
containing a title (h2/h3.job-title) and location span.
"""
from __future__ import annotations

import re

from app.parsers import register_parser

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
    titles = _TITLE_RE.findall(html)
    locations = _LOC_RE.findall(html)
    urls = _URL_RE.findall(html)
    jobs = []
    for i, title_html in enumerate(titles):
        title = _TEXT_RE.sub("", title_html).strip()
        if not title:
            continue
        location = _TEXT_RE.sub("", locations[i]).strip() if i < len(locations) else None
        job_url = urls[i] if i < len(urls) else url
        jobs.append({
            "title": title,
            "company_name": company_name or "",
            "url": job_url,
            "location": location or None,
            "snippet": None,
            "description": None,
            "department": None,
        })
    return jobs
