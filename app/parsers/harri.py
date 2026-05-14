"""Harri parser.

Harri is a JS SPA — Playwright renders it before this parser runs.
URLs follow the pattern: app.harri.com/external/posting/{id}  (detail page)
                         app.harri.com/external/{company}/opening (listing page)

Individual job posting pages often include JSON-LD. Listing pages render
job cards with Harri-specific class patterns.

Strategies in order:
  1. JSON-LD JobPosting structured data (reliable on detail pages)
  2. Rendered job card containers (.opening, [class*='job-posting'], [class*='harri'])
  3. Anchor tags matching /external/posting/ or /opening/ patterns
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from app.parsers import register_parser

_JOB_URL_RE = re.compile(r'/external/(posting|opening)/[^/"\s]+', re.IGNORECASE)
_NAV_RE = re.compile(
    r'^(home|about|contact|login|sign in|menu|back|next|prev|search|'
    r'filter|all jobs|view all|apply now|submit)\s*$',
    re.IGNORECASE,
)
_CARD_CLS = re.compile(r'opening|job.posting|harri.job|job.card|position.card', re.I)
_TITLE_CLS = re.compile(r'job.title|opening.title|position.title|role.title', re.I)
_LOC_CLS = re.compile(r'location|address|city', re.I)


@register_parser("harri.com", [
    ".opening",
    "[class*='job-posting']",
    "[class*='harri-job']",
    "a[href*='/external/posting']",
])
def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")

    # Strategy 1: JSON-LD (most reliable — Harri detail pages emit this)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data])
        for item in items:
            if item.get("@type") == "JobPosting" and item.get("title"):
                loc = None
                job_loc = item.get("jobLocation")
                if isinstance(job_loc, dict):
                    addr = job_loc.get("address", {})
                    loc = ", ".join(filter(None, [addr.get("addressLocality"), addr.get("addressRegion")]))
                elif isinstance(job_loc, list) and job_loc:
                    addr = job_loc[0].get("address", {}) if isinstance(job_loc[0], dict) else {}
                    loc = ", ".join(filter(None, [addr.get("addressLocality"), addr.get("addressRegion")]))
                _add(jobs, seen, item["title"].strip(), item.get("url") or url, url, company_name, location=loc or None)
    if jobs:
        return jobs

    # Strategy 2: rendered job cards
    for card in soup.find_all(True, class_=_CARD_CLS):
        title_el = card.find(True, class_=_TITLE_CLS) or card.find(["h2", "h3", "h4", "strong"])
        link = card.find("a", href=True)
        if not (title_el or link):
            continue
        title = (title_el or link).get_text(separator=" ", strip=True)
        loc_el = card.find(True, class_=_LOC_CLS)
        loc = loc_el.get_text(strip=True) if loc_el else None
        href = link["href"] if link else None
        _add(jobs, seen, title, href, url, company_name, location=loc)
    if jobs:
        return jobs

    # Strategy 3: /external/posting/ or /opening/ anchors
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not _JOB_URL_RE.search(href):
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
