"""ADP Workforce Now parser.

ADP Workforce Now is a React SPA — Playwright renders it before this parser runs.
The listing page at workforcenow.adp.com/mascsr/.../recruitment.html renders job
cards with class names containing 'job' or ADP-specific data attributes.

Strategies in order:
  1. JSON-LD JobPosting structured data
  2. Rendered job card elements ([class*='jobTitle'], [data-testid*='job'])
  3. Anchor tags whose href contains positionId or jobId query params
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from app.parsers import register_parser

_POSITION_URL_RE = re.compile(r'[?&](positionId|jobId|reqId)=', re.IGNORECASE)
_NAV_RE = re.compile(
    r'^(home|about|contact|login|sign in|next|prev|search|filter|'
    r'sort|all jobs|view all|load more|apply now|submit|back)\s*$',
    re.IGNORECASE,
)


@register_parser("workforcenow.adp.com", [
    "[class*='jobTitle']",
    "[class*='job-title']",
    "[data-testid*='job']",
])
def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")

    # Strategy 1: JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data])
        for item in items:
            if item.get("@type") == "JobPosting" and item.get("title"):
                _add(jobs, seen, item["title"].strip(), item.get("url"), url, company_name)
    if jobs:
        return jobs

    # Strategy 2: rendered job cards — ADP uses class names with camelCase 'job' prefixes
    _TITLE_CLS = re.compile(r'job.?title|jobTitle|position.?title', re.I)
    _LOC_CLS = re.compile(r'job.?location|jobLocation|position.?location', re.I)
    _CARD_CLS = re.compile(r'job.?card|jobCard|job.?item|jobItem|job.?row|jobRow|job.?listing', re.I)

    for card in soup.find_all(True, class_=_CARD_CLS):
        title_el = card.find(True, class_=_TITLE_CLS)
        loc_el = card.find(True, class_=_LOC_CLS)
        link = card.find("a", href=True)
        if not (title_el or link):
            continue
        title = (title_el or link).get_text(separator=" ", strip=True)
        href = link["href"] if link else None
        loc = loc_el.get_text(strip=True) if loc_el else None
        _add(jobs, seen, title, href, url, company_name, location=loc)
    if jobs:
        return jobs

    # Strategy 3: anchors with positionId/jobId params
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not _POSITION_URL_RE.search(href):
            continue
        title = link.get_text(separator=" ", strip=True)
        if not title or _NAV_RE.match(title):
            continue
        _add(jobs, seen, title, href, url, company_name)

    return jobs


def _add(jobs, seen, title, href, base_url, company_name, *, location=None):
    if not title or len(title) < 4 or len(title) > 150:
        return
    key = title.lower()
    if key in seen:
        return
    seen.add(key)
    if href and not href.startswith("http"):
        href = urljoin(base_url, href)
    jobs.append({
        "title": title,
        "company_name": company_name or "",
        "url": href,
        "location": location,
        "snippet": None,
        "department": None,
    })
