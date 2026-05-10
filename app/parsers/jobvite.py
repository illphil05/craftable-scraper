"""Jobvite parser — extracts job listings from Jobvite-hosted job board HTML.

Jobvite renders .jv-job-list-name anchor tags inside <li> elements alongside
.jv-job-list-location spans. Parsing per-<li> avoids index-pairing misalignment.
href and class are extracted from <a> tags independently to handle any attribute
ordering in the serialized HTML.
"""
from __future__ import annotations

import re

from app.parsers import register_parser

_ITEM_RE = re.compile(r'<li[^>]*>(.*?)</li>', re.DOTALL | re.IGNORECASE)
_ANCHOR_RE = re.compile(r'<a\b([^>]+)>(.*?)</a>', re.DOTALL | re.IGNORECASE)
_HREF_RE = re.compile(r'\bhref="(/[^"]+)"', re.IGNORECASE)
_CLASS_RE = re.compile(r'\bclass="([^"]*)"', re.IGNORECASE)
_LOC_RE = re.compile(
    r'<span[^>]*class="[^"]*jv-job-list-location[^"]*"[^>]*>(.*?)</span>',
    re.DOTALL | re.IGNORECASE,
)
_TEXT_RE = re.compile(r'<[^>]+>')


@register_parser("jobs.jobvite.com", [])
def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    """Extract job listings from a Jobvite job board page."""
    jobs = []
    for item_m in _ITEM_RE.finditer(html):
        item = item_m.group(1)
        job_anchor = None
        for anchor_m in _ANCHOR_RE.finditer(item):
            attrs = anchor_m.group(1)
            class_m = _CLASS_RE.search(attrs)
            if class_m and "jv-job-list-name" in class_m.group(1):
                job_anchor = anchor_m
                break
        if not job_anchor:
            continue
        href_m = _HREF_RE.search(job_anchor.group(1))
        if not href_m:
            continue
        title = _TEXT_RE.sub("", job_anchor.group(2)).strip()
        if not title:
            continue
        job_url = "https://jobs.jobvite.com" + href_m.group(1)
        loc_m = _LOC_RE.search(item)
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
