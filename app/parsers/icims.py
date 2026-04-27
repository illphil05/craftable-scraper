"""iCIMS ATS parser.

URL pattern: careers.*.com (iCIMS hosted) — often *.icims.com
Job cards use: .iCIMS_JobsTable, .iCIMS_MainWrapper, data-job-id
"""
import re
from urllib.parse import urljoin

from app.parsers import register_parser


@register_parser("icims.com", [".iCIMS_JobsTable", "a[href*='job']"])
def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    # iCIMS job links
    for match in re.finditer(
        r'<a[^>]*href="([^"]*(?:job|requisition|position)[^"]*)"[^>]*>\s*(.*?)\s*</a>',
        html, re.IGNORECASE | re.DOTALL
    ):
        href, title_html = match.group(1), match.group(2)
        title = _clean(title_html)
        _add(jobs, seen, title, href, url, company_name)

    # iCIMS job rows often have title in span with iCIMS_Header class
    for match in re.finditer(
        r'class="[^"]*iCIMS_Header[^"]*"[^>]*>(.*?)<',
        html, re.IGNORECASE | re.DOTALL
    ):
        _add(jobs, seen, _clean(match.group(1)), None, url, company_name)

    # JSON data in page
    for match in re.finditer(r'"jobTitle"\s*:\s*"([^"]{5,120})"', html):
        _add(jobs, seen, match.group(1), None, url, company_name)

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
