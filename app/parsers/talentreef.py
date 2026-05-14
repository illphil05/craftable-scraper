"""TalentReef / JobAppNetwork parser.

TalentReef is a React SPA — Playwright renders it before this parser runs.
Strategies in order:
  1. JSON-LD JobPosting structured data (injected by some deployments)
  2. Rendered job card elements (.job-listing, .job-card, li/div with job links)
  3. Anchor tags matching /apply/ or /job/ URL patterns
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from app.parsers import register_parser

_JOB_URL_RE = re.compile(
    r'/(apply|job|jobs|position|opening|posting)/[^/"\s]+', re.IGNORECASE
)
_NAV_RE = re.compile(
    r'^(home|about|contact|login|sign in|sign up|menu|back|next|prev|search|'
    r'filter|sort|all jobs|view all|load more|apply now|submit)\s*$',
    re.IGNORECASE,
)


@register_parser("jobappnetwork.com", [".job-listing", ".job-card", "[class*='job']"])
def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")

    # Strategy 1: JSON-LD
    import json
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

    # Strategy 2: rendered job card containers
    for sel in (".job-listing", ".job-card", "[class*='job-item']", "[class*='jobItem']"):
        cards = soup.select(sel)
        if not cards:
            continue
        for card in cards:
            link = card.find("a", href=True)
            title_el = card.find(["h2", "h3", "h4", "strong", "span"])
            title = (title_el or link or card).get_text(separator=" ", strip=True) if (title_el or link) else card.get_text(strip=True)
            href = link["href"] if link else None
            _add(jobs, seen, title, href, url, company_name)
        if jobs:
            return jobs

    # Strategy 3: anchor tags with job-pattern URLs
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not _JOB_URL_RE.search(href):
            continue
        title = link.get_text(separator=" ", strip=True)
        if not title or _NAV_RE.match(title):
            continue
        _add(jobs, seen, title, href, url, company_name)

    return jobs


def _add(jobs, seen, title, href, base_url, company_name):
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
        "location": None,
        "snippet": None,
        "department": None,
    })
