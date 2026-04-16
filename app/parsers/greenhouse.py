"""Greenhouse ATS parser.

URL pattern: boards.greenhouse.io/{company}
Greenhouse uses simple, mostly-static HTML — no JS rendering required, but Playwright still works.
"""
import re
from urllib.parse import urljoin


def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    # Greenhouse: <div class="opening"><a href="...">Title</a><span class="location">...</span></div>
    for match in re.finditer(
        r'<div[^>]*class="[^"]*opening[^"]*"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>(.*?)</div>',
        html, re.IGNORECASE | re.DOTALL
    ):
        href, title_html, rest = match.group(1), match.group(2), match.group(3)
        title = _clean(title_html)
        location_match = re.search(r'class="[^"]*location[^"]*"[^>]*>(.*?)<', rest, re.IGNORECASE | re.DOTALL)
        location = _clean(location_match.group(1)) if location_match else None
        _add(jobs, seen, title, href, url, company_name, location=location)

    # Fallback: any links in /jobs/ path
    if not jobs:
        for match in re.finditer(
            r'<a[^>]*href="(/jobs/\d+[^"]*)"[^>]*>(.*?)</a>',
            html, re.IGNORECASE | re.DOTALL
        ):
            href, title_html = match.group(1), match.group(2)
            _add(jobs, seen, _clean(title_html), href, url, company_name)

    return jobs


def _clean(html_fragment: str) -> str:
    text = re.sub(r'<[^>]+>', '', html_fragment).strip()
    return re.sub(r'\s+', ' ', text)


def _add(jobs: list, seen: set, title: str, href: str | None, base_url: str, company_name: str | None, location: str | None = None):
    if not title or len(title) < 4 or len(title) > 150:
        return
    key = title.lower()
    if key in seen:
        return
    seen.add(key)
    full_url = urljoin(base_url, href) if href and not href.startswith('http') else href
    jobs.append({
        "title": title,
        "company_name": company_name or "",
        "url": full_url,
        "location": location,
        "snippet": None,
        "department": None,
    })
