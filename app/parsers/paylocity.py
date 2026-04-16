"""Paylocity ATS parser.

URL pattern: recruiting.paylocity.com/Recruiting/Jobs/...
Job cards are rendered in Angular — Playwright needed for dynamic content.
"""
import re
from urllib.parse import urljoin


def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    # Pattern 1: Job cards with Details/Job links and a job-related class
    matches = re.findall(
        r'<a[^>]*href="([^"]*(?:Details|Job)[^"]*)"[^>]*class="[^"]*job[^"]*"[^>]*>(.*?)</a>',
        html, re.IGNORECASE | re.DOTALL
    )
    for href, title_html in matches:
        title = _clean(title_html)
        _add(jobs, seen, title, href, url, company_name)

    # Pattern 2: Generic job-title-class elements
    for match in re.finditer(
        r'class="[^"]*job[-_]?title[^"]*"[^>]*>(.*?)<',
        html, re.IGNORECASE | re.DOTALL
    ):
        title = _clean(match.group(1))
        _add(jobs, seen, title, None, url, company_name)

    # Pattern 3: Job data in script tags (Angular state hydration)
    for match in re.finditer(r'"title"\s*:\s*"([^"]{5,120})"', html):
        title = match.group(1)
        if not title.startswith(('http', '/', '{', '<')):
            _add(jobs, seen, title, None, url, company_name)

    # Pattern 4: jobName/jobTitle JSON keys
    for match in re.finditer(r'"job(?:Name|Title)"\s*:\s*"([^"]{5,120})"', html):
        _add(jobs, seen, match.group(1), None, url, company_name)

    return jobs


def _clean(html_fragment: str) -> str:
    text = re.sub(r'<[^>]+>', '', html_fragment).strip()
    return re.sub(r'\s+', ' ', text)


def _add(jobs: list, seen: set, title: str, href: str | None, base_url: str, company_name: str | None):
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
        "location": None,
        "snippet": None,
        "department": None,
    })
