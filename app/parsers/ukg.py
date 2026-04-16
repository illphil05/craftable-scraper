"""UKG/Ultipro (UltiPro) ATS parser.

URL pattern:
  - recruiting.ultipro.com/{COMPANY}/JobBoard/{guid}/
  - recruiting2.ultipro.com/{COMPANY}/JobBoard/{guid}/

UltiPro uses Knockout.js to render job cards. After JS hydration the DOM looks like:

  <div data-automation="opportunity" class="opportunity">
    <a data-automation="job-title" class="opportunity-link" href="...OpportunityDetail?opportunityId=UUID">Title</a>
    <small data-automation="opportunity-posted-date">Posted Date</small>
    <span data-automation="job-category">Category</span>
    <span data-automation="job-hours">Full Time</span>
    <div class="location-bottom">
      <candidate-physical-location ...>Location Text</candidate-physical-location>
    </div>
    <div data-automation="job-brief-description">Description</div>
  </div>

Featured jobs appear in a separate table with similar data-automation attributes.

The page also embeds a JS config with jobBoard.Name (company name) and a locations array.
"""
import re
from urllib.parse import urljoin


def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    # Try to extract company name from embedded jobBoard config
    if not company_name:
        company_name = _extract_company_name(html)

    # Strategy 1: Opportunity blocks delimited by <hr class="opportunity-hr"> (primary)
    for match in re.finditer(
        r'<div[^>]*(?:data-automation="opportunity"|class="opportunity")[^>]*>(.*?)<hr[^>]*class="opportunity-hr"',
        html, re.IGNORECASE | re.DOTALL
    ):
        block = match.group(1)
        _parse_opportunity_block(block, jobs, seen, url, company_name)

    # Strategy 2: Direct OpportunityDetail link extraction with surrounding context
    if not jobs:
        for match in re.finditer(
            r'<a[^>]*href="([^"]*OpportunityDetail[^"]*)"[^>]*>(.*?)</a>',
            html, re.IGNORECASE | re.DOTALL
        ):
            href = match.group(1)
            inner = match.group(2)

            # Prefer data-automation="job-title" inside the link for precise title
            title_el = re.search(
                r'data-automation="job-title"[^>]*>([^<]+)<', inner, re.IGNORECASE
            )
            title = _clean(title_el.group(1)) if title_el else _clean(inner)
            if not title:
                continue

            # Try to grab location/category from surrounding context
            pos = match.start()
            context_start = max(0, pos - 200)
            context_end = min(len(html), match.end() + 1500)
            context = html[context_start:context_end]

            location = _extract_location_from_context(context)
            department = _extract_category_from_context(context)
            snippet = _extract_description_from_context(context)

            _add(jobs, seen, title, href, url, company_name,
                 location=location, department=department, snippet=snippet)

    # Strategy 3: Fallback — any anchor with OpportunityDetail in href
    if not jobs:
        for match in re.finditer(
            r'<a[^>]*href="([^"]*OpportunityDetail[^"]*)"[^>]*>([^<]+)</a>',
            html, re.IGNORECASE
        ):
            _add(jobs, seen, _clean(match.group(2)), match.group(1), url, company_name)

    # Strategy 4: Featured opportunities table
    if not jobs:
        for match in re.finditer(
            r'<tr[^>]*data-automation="featured-opportunity"[^>]*>(.*?)</tr>',
            html, re.IGNORECASE | re.DOTALL
        ):
            block = match.group(1)
            link = re.search(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', block, re.DOTALL)
            if not link:
                continue
            href = link.group(1)
            # Title is in <strong data-automation="job-title">
            title_match = re.search(
                r'data-automation="job-title"[^>]*>([^<]+)<', block, re.IGNORECASE
            )
            title = _clean(title_match.group(1)) if title_match else _clean(link.group(2))
            category = _extract_category_from_context(block)
            _add(jobs, seen, title, href, url, company_name, department=category)

    # Strategy 5: JSON state hydration — look for opportunity data in embedded JSON
    if not jobs:
        for match in re.finditer(
            r'"(?:Title|JobTitle|OpportunityTitle)"\s*:\s*"([^"]{5,150})"',
            html
        ):
            title = match.group(1)
            skip_titles = {'career opportunities', 'jobs', 'careers', 'job board', 'opportunities'}
            if title.lower() in skip_titles:
                continue
            _add(jobs, seen, title, None, url, company_name)

    return jobs


def _parse_opportunity_block(block: str, jobs: list, seen: set, base_url: str, company_name: str | None):
    """Parse a single opportunity block for title, link, location, category, description."""
    # Title + link: <a data-automation="job-title" ... href="...">Title</a>
    title_match = re.search(
        r'<a[^>]*(?:data-automation="job-title"|class="[^"]*opportunity-link[^"]*")[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        block, re.IGNORECASE | re.DOTALL
    )
    if not title_match:
        # Fallback: any link with OpportunityDetail
        title_match = re.search(
            r'<a[^>]*href="([^"]*OpportunityDetail[^"]*)"[^>]*>(.*?)</a>',
            block, re.IGNORECASE | re.DOTALL
        )
    if not title_match:
        return

    href = title_match.group(1)
    title = _clean(title_match.group(2))
    if not title:
        return

    location = _extract_location_from_context(block)
    department = _extract_category_from_context(block)
    snippet = _extract_description_from_context(block)

    _add(jobs, seen, title, href, base_url, company_name,
         location=location, department=department, snippet=snippet)


def _extract_location_from_context(context: str) -> str | None:
    """Extract location from various UKG DOM patterns."""
    # Pattern 1: data-automation="physical-location-item" content
    loc = re.search(
        r'data-automation="physical-location-item"[^>]*>(.*?)</(?:candidate-physical-location|div)',
        context, re.IGNORECASE | re.DOTALL
    )
    if loc:
        text = _clean(loc.group(1))
        if text and len(text) > 2:
            return text

    # Pattern 2: location-bottom div content
    loc = re.search(
        r'class="[^"]*location-bottom[^"]*"[^>]*>(.*?)</div>',
        context, re.IGNORECASE | re.DOTALL
    )
    if loc:
        text = _clean(loc.group(1))
        if text and len(text) > 2:
            return text

    # Pattern 3: data-bind with LocationName or PrimaryLocation
    loc = re.search(
        r'(?:LocationName|PrimaryLocation)[^>]*>([^<]+)<',
        context, re.IGNORECASE
    )
    if loc:
        text = _clean(loc.group(1))
        if text and len(text) > 2:
            return text

    # Pattern 4: Look for State, Country pattern in rendered location components
    loc = re.search(
        r'<candidate-physical-location[^>]*>([^<]*(?:<[^/][^>]*>[^<]*)*)</candidate-physical-location>',
        context, re.IGNORECASE | re.DOTALL
    )
    if loc:
        text = _clean(loc.group(1))
        if text and len(text) > 2:
            return text

    return None


def _extract_category_from_context(context: str) -> str | None:
    """Extract job category/department from UKG DOM."""
    # Pattern 1: data-automation="job-category" (may have nested spans, or be small/span)
    cat = re.search(
        r'data-automation="job-category"[^>]*>(.*?)</(?:span|small|div)',
        context, re.IGNORECASE | re.DOTALL
    )
    if cat:
        text = _clean(cat.group(1))
        if text and len(text) > 2:
            return text

    # Pattern 2: text after "Job Category:" label
    cat = re.search(
        r'Job\s*Category[^:]*:\s*</(?:strong|span|label)>\s*(?:<[^>]+>)*([^<]+)<',
        context, re.IGNORECASE
    )
    if cat:
        text = _clean(cat.group(1))
        if text and len(text) > 2:
            return text

    # Pattern 3: Knockout-bound category span
    cat = re.search(
        r'data-bind="text:\s*JobCategoryName[^"]*"[^>]*>([^<]+)<',
        context, re.IGNORECASE
    )
    if cat:
        text = _clean(cat.group(1))
        if text and len(text) > 2:
            return text

    return None


def _extract_description_from_context(context: str) -> str | None:
    """Extract brief description from UKG DOM."""
    desc = re.search(
        r'data-automation="job-brief-description"[^>]*>(.*?)</div>',
        context, re.IGNORECASE | re.DOTALL
    )
    if desc:
        text = _clean(desc.group(1))
        if text and len(text) > 5:
            return text[:500]
    return None


def _extract_company_name(html: str) -> str | None:
    """Extract company name from embedded jobBoard config JSON."""
    # Look for jobBoard: {"Name":"Company Name",...}
    match = re.search(
        r'jobBoard:\s*\{[^}]*"Name"\s*:\s*"([^"]+)"',
        html, re.IGNORECASE
    )
    if match:
        name = match.group(1)
        # Strip common suffixes like "Opportunities", "Careers", "Jobs"
        name = re.sub(r'\s*(Opportunities|Careers|Jobs|Job Board|Career)\s*$', '', name, flags=re.IGNORECASE).strip()
        if name:
            return name

    # Fallback: page title
    match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    if match:
        title = _clean(match.group(1))
        title = re.sub(r'\s*[-|]\s*(Careers?|Jobs?|Opportunities).*$', '', title, flags=re.IGNORECASE).strip()
        if title and len(title) > 2:
            return title

    return None


def _clean(html_fragment: str) -> str:
    text = re.sub(r'<[^>]+>', '', html_fragment).strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('&amp;', '&').replace('&#39;', "'").replace('&quot;', '"').replace('&nbsp;', ' ')
    return text


def _add(jobs: list, seen: set, title: str, href: str | None, base_url: str,
         company_name: str | None, location: str | None = None,
         department: str | None = None, snippet: str | None = None):
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
        "snippet": snippet,
        "department": department,
    })
