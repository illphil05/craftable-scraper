"""Lever ATS parser.

URL pattern: jobs.lever.co/{company}
Lever uses simple HTML with .posting-title, .posting-name, etc.
"""
import re
from urllib.parse import urljoin


def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    # Lever: <a class="posting-title" href="..."><h5>Title</h5><span>Location</span></a>
    for match in re.finditer(
        r'<a[^>]*class="[^"]*posting-title[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html, re.IGNORECASE | re.DOTALL
    ):
        href, inner = match.group(1), match.group(2)
        # Title is usually in h5 or div
        title_match = re.search(r'<(?:h\d|div)[^>]*data-qa="posting-name"[^>]*>(.*?)</', inner, re.DOTALL)
        if not title_match:
            title_match = re.search(r'<h\d[^>]*>(.*?)</h\d>', inner, re.DOTALL)
        if not title_match:
            title_match = re.search(r'>([^<]+)<', inner)
        title = _clean(title_match.group(1)) if title_match else _clean(inner)

        location_match = re.search(r'class="[^"]*sort-by-location[^"]*"[^>]*>(.*?)<', inner, re.IGNORECASE | re.DOTALL)
        location = _clean(location_match.group(1)) if location_match else None

        _add(jobs, seen, title, href, url, company_name, location=location)

    # Fallback: alternative posting class names
    if not jobs:
        for match in re.finditer(
            r'<a[^>]*href="(https?://jobs\.lever\.co/[^"]+)"[^>]*>(.*?)</a>',
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
