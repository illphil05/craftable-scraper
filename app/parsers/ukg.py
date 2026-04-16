"""UKG/Ultipro (UltiPro) ATS parser.

URL pattern:
  - recruiting.ultipro.com/{COMPANY}/JobBoard/{guid}/
  - recruiting2.ultipro.com/{COMPANY}/JobBoard/{guid}/
  - {COMPANY}.ultipro.com/...

UltiPro is a heavy Angular/React app — Playwright must let JS hydrate.
Job cards typically render as:
  <a href="/{COMPANY}/JobBoard/{guid}/OpportunityDetail?opportunityId={id}">
    <span class="opportunity-link-text">Title</span>
  </a>
  <span data-bind="text: PrimaryLocation.LocationName">City, ST</span>

Falls back to JSON state hydration patterns if React hasn't rendered DOM cards.
"""
import re
from urllib.parse import urljoin


def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    # Strategy 1: Opportunity links with title spans
    # <a href="...OpportunityDetail?opportunityId=12345"...><span ...>Title</span></a>
    for match in re.finditer(
        r'<a[^>]*href="([^"]*OpportunityDetail[^"]*)"[^>]*>(.*?)</a>',
        html, re.IGNORECASE | re.DOTALL
    ):
        href = match.group(1)
        inner = match.group(2)
        title = _clean(inner)
        if title:
            _add(jobs, seen, title, href, url, company_name)

    # Strategy 2: Class-based opportunity cards
    # <div class="opportunity-card">...<a>Title</a>...<span class="...location">Loc</span>...</div>
    for match in re.finditer(
        r'<(?:div|li|article)[^>]*class="[^"]*opportunity[^"]*"[^>]*>(.*?)</(?:div|li|article)>',
        html, re.IGNORECASE | re.DOTALL
    ):
        block = match.group(1)
        link = re.search(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', block, re.DOTALL)
        if not link:
            continue
        href = link.group(1)
        title = _clean(link.group(2))
        loc_match = re.search(
            r'class="[^"]*(?:location|opportunity-location)[^"]*"[^>]*>(.*?)<',
            block, re.IGNORECASE | re.DOTALL
        )
        location = _clean(loc_match.group(1)) if loc_match else None
        _add(jobs, seen, title, href, url, company_name, location=location)

    if jobs:
        return jobs

    # Strategy 3: JSON state hydration — UltiPro embeds opportunities as JSON
    # Common keys: "Title", "JobTitle", "OpportunityTitle"
    for match in re.finditer(
        r'"(?:Title|JobTitle|OpportunityTitle)"\s*:\s*"([^"]{5,150})"',
        html
    ):
        title = match.group(1)
        # Skip page metadata titles ("Career Opportunities", etc.)
        if title.lower() in ('career opportunities', 'jobs', 'careers', 'job board', 'opportunities'):
            continue
        _add(jobs, seen, title, None, url, company_name)

    # Strategy 4: Fallback — any anchor containing "OpportunityDetail" even without a class match
    if not jobs:
        for match in re.finditer(
            r'<a[^>]*href="([^"]*OpportunityDetail[^"]*)"[^>]*>([^<]+)</a>',
            html, re.IGNORECASE
        ):
            _add(jobs, seen, _clean(match.group(2)), match.group(1), url, company_name)

    return jobs


def _clean(html_fragment: str) -> str:
    text = re.sub(r'<[^>]+>', '', html_fragment).strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('&amp;', '&').replace('&#39;', "'").replace('&quot;', '"').replace('&nbsp;', ' ')
    return text


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
