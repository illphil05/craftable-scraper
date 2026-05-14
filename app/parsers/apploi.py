"""Apploi parser.

Apploi is a JS SPA — Playwright renders it before this parser runs.
URLs follow the pattern: apploi.com/job/{id}  (individual job detail pages)

Apploi pages are individual job postings, not listing pages. The parser
extracts a single job from the rendered detail page.

Strategies in order:
  1. JSON-LD JobPosting structured data
  2. Rendered h1/h2 title with adjacent location elements
  3. og:title meta tag as last resort
"""
from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup
from app.parsers import register_parser

_LOC_CLS = re.compile(r'location|address|city', re.I)
_TITLE_CLS = re.compile(r'job.title|position.title|role.title|opening.title', re.I)


@register_parser("apploi.com", [
    "h1",
    "[class*='job-title']",
    "[class*='position-title']",
])
def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
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
                title = item["title"].strip()
                loc = None
                job_loc = item.get("jobLocation")
                if isinstance(job_loc, dict):
                    addr = job_loc.get("address", {})
                    loc = ", ".join(filter(None, [addr.get("addressLocality"), addr.get("addressRegion")]))
                description = item.get("description", "")
                snippet = re.sub(r'<[^>]+>', ' ', description).strip()[:500] if description else None
                return [{"title": title, "company_name": company_name or item.get("hiringOrganization", {}).get("name") or "", "url": url, "location": loc or None, "snippet": snippet, "department": None}]

    # Strategy 2: rendered h1/h2 title
    title_el = soup.find(True, class_=_TITLE_CLS) or soup.find("h1") or soup.find("h2")
    if title_el:
        title = title_el.get_text(separator=" ", strip=True)
        if title and 4 <= len(title) <= 150:
            loc_el = soup.find(True, class_=_LOC_CLS)
            loc = loc_el.get_text(strip=True) if loc_el else None
            return [{"title": title, "company_name": company_name or "", "url": url, "location": loc, "snippet": None, "department": None}]

    # Strategy 3: og:title
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
        # Strip common "Apply for X at Y" or "X - Y" patterns
        title = re.sub(r'\s*[-–|]\s*.+$', '', title).strip()
        if title and 4 <= len(title) <= 150:
            return [{"title": title, "company_name": company_name or "", "url": url, "location": None, "snippet": None, "department": None}]

    return []
