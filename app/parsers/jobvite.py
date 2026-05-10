"""Jobvite parser — extracts job listings from Jobvite-hosted job board HTML.

Jobvite renders .jv-job-list-name anchor tags inside <li> elements alongside
.jv-job-list-location spans. Parsing per-<li> avoids index-pairing misalignment
when a job has no location span.
"""
from __future__ import annotations

import re

from app.parsers import register_parser

_ITEM_RE = re.compile(r'<li[^>]*>(.*?)</li>', re.DOTALL | re.IGNORECASE)
_JOB_RE = re.compile(
    r'<a[^>]+href="(/[^"]+)"[^>]*class="[^"]*jv-job-list-name[^"]*"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
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
        job_m = _JOB_RE.search(item)
        if not job_m:
            continue
        href, title_html = job_m.group(1), job_m.group(2)
        title = _TEXT_RE.sub("", title_html).strip()
        if not title:
            continue
        job_url = "https://jobs.jobvite.com" + href
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
