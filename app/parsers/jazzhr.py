"""JazzHR / ApplyToJob parser.

JazzHR powers two URL surfaces:
  - applytojob.com/{company}/apply/  (white-label listing pages, SSR)
  - app.jazz.co/apply/{company}/     (hosted listing pages, SSR)

Both render the same HTML structure with .opening job cards.

Strategies in order:
  1. JSON-LD JobPosting structured data
  2. .opening card containers (JazzHR canonical DOM)
  3. Anchor tags matching /apply/ URL patterns
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from app.parsers import register_parser

_JOB_URL_RE = re.compile(r'/apply/[^/"\s]+/[^/"\s]+', re.IGNORECASE)
_NAV_RE = re.compile(
    r'^(home|about|contact|login|sign in|sign up|menu|back|next|prev|search|'
    r'filter|sort|all jobs|view all|load more|apply now|submit)\s*$',
    re.IGNORECASE,
)


@register_parser("applytojob.com", [".opening", ".opening-title", "#openings"])
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

    # Strategy 2: JazzHR .opening cards
    for card in soup.find_all(class_="opening"):
        title_el = card.find(class_=re.compile(r"opening.job.title|opening-title", re.I))
        link = card.find("a", href=True)
        title_text = (title_el or link or card).get_text(separator=" ", strip=True) if (title_el or link) else card.get_text(strip=True)
        dept_el = card.find(class_=re.compile(r"opening.department", re.I))
        loc_el = card.find(class_=re.compile(r"opening.location", re.I))
        href = link["href"] if link else None
        dept = dept_el.get_text(strip=True) if dept_el else None
        loc = loc_el.get_text(strip=True) if loc_el else None
        _add(jobs, seen, title_text, href, url, company_name, department=dept, location=loc)
    if jobs:
        return jobs

    # Strategy 3: anchor tags with /apply/ URL pattern
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not _JOB_URL_RE.search(href):
            continue
        title = link.get_text(separator=" ", strip=True)
        if not title or _NAV_RE.match(title):
            continue
        _add(jobs, seen, title, href, url, company_name)

    return jobs


def _add(jobs, seen, title, href, base_url, company_name, *, department=None, location=None):
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
        "department": department,
    })
