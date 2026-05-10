"""Taleo parser — extracts job listings from Taleo-hosted job board HTML.

Taleo renders a <table> with rows containing job title anchors with
class="jobTitle" and location spans with class="jobLocation". href and class
are extracted independently to handle any attribute ordering.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse as _up, urljoin

from app.parsers import register_parser

_ROW_RE = re.compile(r'<tr\b[^>]*>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
_ANCHOR_RE = re.compile(r'<a\b([^>]+)>(.*?)</a>', re.DOTALL | re.IGNORECASE)
_HREF_RE = re.compile(r'\bhref="([^"]+)"', re.IGNORECASE)
_CLASS_RE = re.compile(r'\bclass="([^"]*)"', re.IGNORECASE)
_LOC_RE = re.compile(r'<span[^>]*class="[^"]*jobLocation[^"]*"[^>]*>(.*?)</span>', re.DOTALL | re.IGNORECASE)
_TEXT_RE = re.compile(r'<[^>]+>')


@register_parser("taleo.net", [])
def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    """Extract job listings from a Taleo job board page."""
    parsed = _up(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    jobs = []
    for row_m in _ROW_RE.finditer(html):
        row = row_m.group(1)
        title_anchor = None
        for anchor_m in _ANCHOR_RE.finditer(row):
            attrs = anchor_m.group(1)
            class_m = _CLASS_RE.search(attrs)
            if class_m and "jobTitle" in class_m.group(1):
                title_anchor = anchor_m
                break
        if not title_anchor:
            continue
        href_m = _HREF_RE.search(title_anchor.group(1))
        if not href_m:
            continue
        title = _TEXT_RE.sub("", title_anchor.group(2)).strip()
        if not title:
            continue
        job_url = urljoin(base, href_m.group(1))
        loc_m = _LOC_RE.search(row)
        location = (_TEXT_RE.sub("", loc_m.group(1)).strip() or None) if loc_m else None
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
