"""Dayforce HCM parser — extracts job data from Next.js __NEXT_DATA__ blob.

URL pattern: jobs.dayforcehcm.com/en-US/{namespace}/{careerSite}/jobs/{jobId}

Dayforce is a Next.js SSR application. Every job detail page embeds the full
job record as JSON inside <script id="__NEXT_DATA__">. This parser handles
detail pages only (URLs ending in /jobs/{id}). Listing pages (/jobs with no
ID) have a different pageProps shape and no jobData key — they return [].
Missing or malformed __NEXT_DATA__ also returns [].

postingStatus == 4 means expired/closed — returns [] in that case.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser

from app.parsers import register_parser

_POSTING_STATUS_CLOSED = 4
_BLOCK_TAGS = frozenset({"p", "br", "li", "div", "h1", "h2", "h3", "h4", "h5", "h6"})


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in _BLOCK_TAGS:
            self._parts.append(" ")

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self._parts)).strip()


def _strip_html(html_text: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html_text)
    return stripper.get_text()


def _extract_next_data(html: str) -> dict | None:
    m = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return None


def _build_location(posting_locations: list[dict]) -> str | None:
    names = [
        loc.get("name") or loc.get("locationName")
        for loc in posting_locations
        if isinstance(loc, dict)
    ]
    names = [n for n in names if n]
    return "; ".join(names) if names else None


@register_parser("dayforcehcm.com", [])
def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    next_data = _extract_next_data(html)
    if not next_data:
        return []

    try:
        job_data = next_data["props"]["pageProps"]["jobData"]
    except (KeyError, TypeError):
        return []

    if not isinstance(job_data, dict):
        return []

    if job_data.get("postingStatus") == _POSTING_STATUS_CLOSED:
        return []

    title = job_data.get("jobTitle") or ""
    if not title:
        return []

    posting_locations = job_data.get("postingLocations") or []
    location = _build_location(posting_locations)

    content = job_data.get("jobPostingContent") or {}
    description_html = content.get("jobDescription") or None
    description_text = _strip_html(description_html) if description_html else None
    snippet = description_text[:500] if description_text else None

    req_id = job_data.get("jobReqId") or None

    posted_raw = job_data.get("postingStartTimestampUTC") or None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", posted_raw) if posted_raw else None
    posted_date = m.group(1) if m else None

    return [
        {
            "title": title,
            "company_name": company_name or "",
            "url": url,
            "location": location,
            "snippet": snippet,
            "description": description_text,
            "department": None,
            "requisition_id": req_id,
            "posted_date": posted_date,
        }
    ]
