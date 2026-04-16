"""Greenhouse ATS parser.

URL pattern: boards.greenhouse.io/{company} or boards.greenhouse.io/embed/job_board?for={company}

Modern Greenhouse uses React with classes like:
  - tr.job-post / div.job-post (each job row)
  - div.opening (legacy)
  - a[href*='/jobs/'] (job detail links)
"""
import re
from urllib.parse import urljoin


def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    # Modern Greenhouse: <tr class="job-post"><td><a href="/jobs/123">Title</a><span>Location</span></td></tr>
    for match in re.finditer(
        r'<(?:tr|div)[^>]*class="[^"]*job-post[^"]*"[^>]*>(.*?)</(?:tr|div)>',
        html, re.IGNORECASE | re.DOTALL
    ):
        block = match.group(1)
        link_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
        if not link_match:
            continue
        href = link_match.group(1)
        title = _clean(link_match.group(2))
        # Try to extract location from a sibling element
        loc_match = re.search(r'<(?:span|p)[^>]*class="[^"]*location[^"]*"[^>]*>(.*?)<', block, re.IGNORECASE | re.DOTALL)
        if not loc_match:
            # Greenhouse often has location in a <p> or <span> after the title
            loc_match = re.search(r'</a>\s*<(?:span|p)[^>]*>(.*?)<', block, re.DOTALL)
        location = _clean(loc_match.group(1)) if loc_match else None
        _add(jobs, seen, title, href, url, company_name, location=location)

    if jobs:
        return jobs

    # Legacy: <div class="opening"><a href="...">Title</a><span class="location">...</span></div>
    for match in re.finditer(
        r'<div[^>]*class="[^"]*opening[^"]*"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>(.*?)</div>',
        html, re.IGNORECASE | re.DOTALL
    ):
        href, title_html, rest = match.group(1), match.group(2), match.group(3)
        title = _clean(title_html)
        location_match = re.search(r'class="[^"]*location[^"]*"[^>]*>(.*?)<', rest, re.IGNORECASE | re.DOTALL)
        location = _clean(location_match.group(1)) if location_match else None
        _add(jobs, seen, title, href, url, company_name, location=location)

    if jobs:
        return jobs

    # Fallback: any anchor pointing at /jobs/{id}
    for match in re.finditer(
        r'<a[^>]*href="([^"]*/jobs/\d+[^"]*)"[^>]*>(.*?)</a>',
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
