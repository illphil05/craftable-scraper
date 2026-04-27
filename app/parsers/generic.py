"""Generic parser — works on any HTML page with job listing links.

Falls back from JSON-LD structured data → href patterns → keyword matches.
Rewrote HTML traversal to use BeautifulSoup for robustness.
"""
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

JOB_KEYWORDS = re.compile(
    r'(?i)(manager|director|coordinator|analyst|specialist|controller|accountant|chef|'
    r'supervisor|engineer|assistant|officer|buyer|purchas|server|host|bartender|'
    r'housekeeper|concierge|valet|sommelier|steward|associate|representative|'
    r'cook|attendant|administrator|executive|president|vice president|vp\b)'
)

NAV_PATTERN = re.compile(
    r'^(home|about|contact|login|sign\s*(in|up)?|menu|close|back|next|prev|search|filter|sort|'
    r'page|view|show|load|more|all|see|find|español|français|english|deutsch|'
    r'jobs?\s+(by|search)|recently\s+posted|featured|browse|categories|locations?|departments?|apply|'
    r'remote\s+jobs?|find\s+jobs?|filter\s+results?|reset|clear)\b', re.IGNORECASE
)

JOB_URL_PATTERN = re.compile(
    r'/(jobs?|positions?|openings?|careers?|requisitions?|posting|apply)/[^/]+/?$'
    r'|/(jobs?|positions?|openings?|careers?|requisitions?|posting)/\d+',
    re.IGNORECASE,
)


def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    # Strategy 1: JSON-LD JobPosting structured data (most reliable)
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and data.get("@graph"):
            items = data["@graph"]
        else:
            items = [data]
        for item in items:
            if item.get("@type") == "JobPosting" and item.get("title"):
                raw_loc = item.get("jobLocation")
                job_url = item.get("url") or (raw_loc if isinstance(raw_loc, str) else None)
                _add(jobs, seen, item["title"].strip(), job_url, url, company_name)
    if jobs:
        return jobs

    # Strategy 2: Anchor tags with job-like URLs or job-keyword titles
    for link in soup.find_all("a", href=True):
        href = link["href"]
        title = link.get_text(separator=" ", strip=True)
        if not title or len(title) < 5 or len(title) > 150:
            continue
        if NAV_PATTERN.match(title):
            continue
        has_job_url = bool(JOB_URL_PATTERN.search(href))
        has_job_title = bool(JOB_KEYWORDS.search(title))
        if has_job_url or has_job_title:
            _add(jobs, seen, title, href, url, company_name)

    return jobs


def _add(jobs: list, seen: set, title: str, href: str | None, base_url: str, company_name: str | None):
    if not title or len(title) < 4 or len(title) > 150:
        return
    key = title.lower()
    if key in seen:
        return
    seen.add(key)
    full_url = urljoin(base_url, href) if href and not href.startswith("http") else href
    jobs.append({
        "title": title,
        "company_name": company_name or "",
        "url": full_url,
        "location": None,
        "snippet": None,
        "department": None,
    })
