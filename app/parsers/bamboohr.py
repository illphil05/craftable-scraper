"""BambooHR parser.

BambooHR job boards are React SPAs — Playwright renders them before this parser
runs. After rendering the listing page ({subdomain}.bamboohr.com/jobs/), the DOM
contains either the classic .ResposiveTable layout or the newer
BambooHR-ATS-Jobs-item list.

Strategies in order:
  1. JSON-LD JobPosting structured data
  2. .BambooHR-ATS-Jobs-item list (newer UI)
  3. .ResposiveTable rows (classic UI)
  4. Anchor tags matching /jobs/view.php?id= patterns
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from app.parsers import register_parser

_JOB_URL_RE = re.compile(r'/jobs/view\.php\?id=\d+', re.IGNORECASE)


@register_parser("bamboohr.com", [
    ".BambooHR-ATS-Jobs-item",
    ".ResposiveTable",
    "a[href*='view.php']",
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

    # Strategy 2: newer BambooHR-ATS-Jobs-item list — match <li> only to avoid
    # matching child elements like BambooHR-ATS-Jobs-item-title/-location/-department
    for item in soup.find_all("li", class_=re.compile(r"BambooHR-ATS-Jobs-item", re.I)):
        link = item.find("a", href=True)
        title_el = item.find(class_=re.compile(r"BambooHR-ATS-Jobs-item-title|job.title", re.I))
        loc_el = item.find(class_=re.compile(r"BambooHR-ATS-Jobs-item-location|location", re.I))
        dept_el = item.find(class_=re.compile(r"BambooHR-ATS-Jobs-item-department|department", re.I))
        title = (title_el or link or item).get_text(separator=" ", strip=True) if (title_el or link) else item.get_text(strip=True)
        href = link["href"] if link else None
        loc = loc_el.get_text(strip=True) if loc_el else None
        dept = dept_el.get_text(strip=True) if dept_el else None
        _add(jobs, seen, title, href, url, company_name, location=loc, department=dept)
    if jobs:
        return jobs

    # Strategy 3: classic .ResposiveTable rows (note: typo is intentional in BambooHR CSS)
    table = soup.find(class_=re.compile(r"ResposiveTable|BambooHR-ATS-board", re.I))
    if table:
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue
            link = cells[0].find("a", href=True)
            if not link:
                continue
            title = link.get_text(strip=True)
            href = link["href"]
            loc = cells[1].get_text(strip=True) if len(cells) > 1 else None
            dept = cells[2].get_text(strip=True) if len(cells) > 2 else None
            _add(jobs, seen, title, href, url, company_name, location=loc, department=dept)
        if jobs:
            return jobs

    # Strategy 4: /jobs/view.php?id= anchors
    for link in soup.find_all("a", href=True):
        if not _JOB_URL_RE.search(link["href"]):
            continue
        title = link.get_text(separator=" ", strip=True)
        _add(jobs, seen, title, link["href"], url, company_name)

    return jobs


def _add(jobs, seen, title, href, base_url, company_name, *, location=None, department=None):
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
