"""Ashby parser — extracts job data from __NEXT_DATA__ JSON blob.

Ashby job boards (jobs.ashbyhq.com) are Next.js SSR applications. Job data is
embedded in the page HTML as a __NEXT_DATA__ JSON blob under
props.pageProps.jobBoard.jobPostings.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse as _up

from app.parsers import register_parser

_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


@register_parser("jobs.ashbyhq.com", [])
def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    """Extract job listings from an Ashby job board page."""
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
        postings = data["props"]["pageProps"]["jobBoard"]["jobPostings"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []

    # parse org slug from url: jobs.ashbyhq.com/{org}/... or custom domain root
    parsed_url = _up(url)
    origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
    parts = parsed_url.path.strip("/").split("/")
    org = parts[0] if parts and parts[0] else ""

    jobs = []
    for p in postings:
        title = p.get("title") or ""
        if not title:
            continue
        job_id = p.get("id") or ""
        job_url = f"{origin}/{org}/{job_id}" if org and job_id else url
        jobs.append({
            "title": title,
            "company_name": company_name or "",
            "url": job_url,
            "location": p.get("locationName") or None,
            "department": p.get("departmentName") or None,
            "snippet": None,
            "description": None,
        })
    return jobs
