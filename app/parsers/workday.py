"""Workday ATS parser.

URL pattern: *.myworkdayjobs.com/...
Workday is a heavy SPA — uses data-automation-id attributes for job rows.
"""
import re
from urllib.parse import urljoin


def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    # Workday job titles use data-automation-id="jobTitle"
    for match in re.finditer(
        r'data-automation-id="jobTitle"[^>]*>(.*?)</[^>]+>',
        html, re.IGNORECASE | re.DOTALL
    ):
        _add(jobs, seen, _clean(match.group(1)), None, url, company_name)

    # Workday job links often look like /jobs/{requisition-id}
    for match in re.finditer(
        r'<a[^>]*href="([^"]*/job/[^"]+)"[^>]*data-automation-id="jobTitle"[^>]*>(.*?)</a>',
        html, re.IGNORECASE | re.DOTALL
    ):
        href, title_html = match.group(1), match.group(2)
        _add(jobs, seen, _clean(title_html), href, url, company_name)

    # Generic job links to /job/ paths
    for match in re.finditer(
        r'<a[^>]*href="([^"]*/job/[^"]+)"[^>]*>(.*?)</a>',
        html, re.IGNORECASE | re.DOTALL
    ):
        href, title_html = match.group(1), match.group(2)
        _add(jobs, seen, _clean(title_html), href, url, company_name)

    # JSON data in script tags
    for match in re.finditer(r'"title"\s*:\s*"([^"]{5,120})"', html):
        title = match.group(1)
        if not title.startswith(('http', '/', '{', '<')):
            _add(jobs, seen, title, None, url, company_name)

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
