"""SmartRecruiters ATS parser.

URL pattern:
  - jobs.smartrecruiters.com/{company}
  - careers.smartrecruiters.com/{company}/...
  - {company}.smartrecruiters.com/...

The public job board renders job cards as:
  <li class="opening-job job">
    <a class="link--block details" href="/{company}/{jobId}-{slug}">
      <h4 class="details-title job-title link--block-target">Title</h4>
      <ul class="job-desc">
        <li>City, Country</li>
        <li>Department</li>
      </ul>
    </a>
  </li>

Newer career sites use plain <a href="/{company}/..."> with structured JSON-LD.
"""
import re
from urllib.parse import urljoin


def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    # Strategy 1: Classic opening-job list items
    for match in re.finditer(
        r'<li[^>]*class="[^"]*opening-job[^"]*"[^>]*>(.*?)</li>',
        html, re.IGNORECASE | re.DOTALL
    ):
        block = match.group(1)
        link = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
        if not link:
            continue
        href = link.group(1)
        link_inner = link.group(2)

        title_match = re.search(
            r'<(?:h\d|span)[^>]*class="[^"]*(?:details-title|job-title|title)[^"]*"[^>]*>(.*?)</(?:h\d|span)>',
            link_inner, re.IGNORECASE | re.DOTALL
        )
        title = _clean(title_match.group(1)) if title_match else _clean(link_inner)

        # Extract location + department from job-desc list
        location, department = None, None
        desc_items = re.findall(
            r'<li[^>]*>(.*?)</li>',
            link_inner, re.IGNORECASE | re.DOTALL
        )
        if desc_items:
            location = _clean(desc_items[0]) if len(desc_items) >= 1 else None
            department = _clean(desc_items[1]) if len(desc_items) >= 2 else None

        _add(jobs, seen, title, href, url, company_name, location=location, department=department)

    if jobs:
        return jobs

    # Strategy 2: JSON-LD structured data (most reliable for newer sites)
    # SmartRecruiters embeds JobPosting JSON-LD blocks
    for match in re.finditer(
        r'"@type"\s*:\s*"JobPosting"[^}]*?"title"\s*:\s*"([^"]+)"[^}]*?(?:"jobLocation"[^}]*?"addressLocality"\s*:\s*"([^"]+)")?',
        html, re.DOTALL
    ):
        title = match.group(1).strip()
        location = match.group(2).strip() if match.group(2) else None
        _add(jobs, seen, title, None, url, company_name, location=location)

    if jobs:
        return jobs

    # Strategy 3: Job-anchor pattern with details class
    for match in re.finditer(
        r'<a[^>]*class="[^"]*(?:link--block|details|job-card)[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html, re.IGNORECASE | re.DOTALL
    ):
        href = match.group(1)
        inner = match.group(2)
        title_match = re.search(r'<(?:h\d|span)[^>]*>(.*?)</(?:h\d|span)>', inner, re.DOTALL)
        title = _clean(title_match.group(1)) if title_match else _clean(inner)
        _add(jobs, seen, title, href, url, company_name)

    return jobs


def _clean(html_fragment: str) -> str:
    text = re.sub(r'<[^>]+>', '', html_fragment).strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('&amp;', '&').replace('&#39;', "'").replace('&quot;', '"').replace('&nbsp;', ' ')
    return text


def _add(jobs: list, seen: set, title: str, href: str | None, base_url: str, company_name: str | None, location: str | None = None, department: str | None = None):
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
        "department": department,
    })
