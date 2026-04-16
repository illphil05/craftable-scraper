"""Generic parser — works on any HTML page with job listing links.

Falls back from JSON-LD structured data → href patterns → keyword matches.
"""
import re
from urllib.parse import urljoin

JOB_KEYWORDS = re.compile(
    r'(?i)(manager|director|coordinator|analyst|specialist|controller|accountant|chef|'
    r'supervisor|engineer|assistant|officer|buyer|purchas|server|host|bartender|'
    r'housekeeper|concierge|valet|sommelier|steward|associate|representative|'
    r'cook|attendant|administrator|executive|president|vice president|vp\b)'
)

NAV_PATTERN = re.compile(
    r'^(home|about|contact|login|sign|menu|close|back|next|prev|search|filter|sort|'
    r'page|view|show|load|more|all|see|find|español|français|english|deutsch|'
    r'jobs?\s+by|recently|featured|browse|categories|locations|departments|apply|'
    r'remote\s+jobs?)$', re.IGNORECASE
)

JOB_URL_PATTERN = re.compile(r'/(job|position|opening|career|requisition|apply|posting)', re.IGNORECASE)


def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    # Strategy 1: JSON-LD JobPosting structured data (most reliable)
    for match in re.finditer(
        r'"@type"\s*:\s*"JobPosting".*?"title"\s*:\s*"([^"]+)"',
        html, re.DOTALL
    ):
        _add(jobs, seen, match.group(1).strip(), None, url, company_name)
    if jobs:
        return jobs

    # Strategy 2: Anchor tags with job-like URLs or job-keyword titles
    for match in re.finditer(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL):
        href, link_html = match.group(1), match.group(2)
        title = _clean(link_html)
        if not title or len(title) < 5 or len(title) > 150:
            continue
        if NAV_PATTERN.match(title):
            continue
        has_job_url = bool(JOB_URL_PATTERN.search(href))
        has_job_title = bool(JOB_KEYWORDS.search(title))
        if has_job_url or has_job_title:
            _add(jobs, seen, title, href, url, company_name)

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
