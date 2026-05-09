"""Jobvite parser — extracts job listings from Jobvite-hosted job board HTML.

Jobvite renders .jv-job-list-name anchor tags with job titles and relative
href values like /company/careers/jobs/XXX.
"""
from __future__ import annotations

import re

from app.parsers import register_parser

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
    locations = _LOC_RE.findall(html)
    for i, m in enumerate(_JOB_RE.finditer(html)):
        href, title_html = m.group(1), m.group(2)
        title = _TEXT_RE.sub("", title_html).strip()
        if not title:
            continue
        job_url = "https://jobs.jobvite.com" + href
        location = _TEXT_RE.sub("", locations[i]).strip() if i < len(locations) else None
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
