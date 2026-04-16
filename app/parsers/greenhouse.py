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

    # Modern Greenhouse: <tr class="job-post"><td><a href="/jobs/123"><p class="body--medium">Title</p><span class="badge">New</span><p class="body__secondary">Location</p></a></td></tr>
    for match in re.finditer(
        r'<(?:tr|div)[^>]*class="[^"]*job-post[^"]*"[^>]*>(.*?)</(?:tr|div)>',
        html, re.IGNORECASE | re.DOTALL
    ):
        block = match.group(1)
        link_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
        if not link_match:
            continue
        href = link_match.group(1)
        link_inner = link_match.group(2)

        # Try to find title in a specific child (p, h2, h3 with "title" or "body--medium" or "name" class)
        title = None
        for title_re in [
            r'<(?:p|h\d|span)[^>]*class="[^"]*(?:body--medium|title|name|posting-name)[^"]*"[^>]*>(.*?)</(?:p|h\d|span)>',
            r'<p[^>]*>(.*?)</p>',
            r'<h\d[^>]*>(.*?)</h\d>',
        ]:
            tm = re.search(title_re, link_inner, re.IGNORECASE | re.DOTALL)
            if tm:
                candidate = _clean(tm.group(1))
                # Skip badge text like "New" or single words
                if candidate and len(candidate) > 3 and candidate.lower() not in ('new', 'apply', 'remote'):
                    title = candidate
                    break
        if not title:
            title = _clean(link_inner)

        # Location: secondary text or .location class, often after the title
        location = None
        loc_match = re.search(r'<(?:p|span|div)[^>]*class="[^"]*(?:location|body__secondary|secondary|location-tag)[^"]*"[^>]*>(.*?)</(?:p|span|div)>', block, re.IGNORECASE | re.DOTALL)
        if loc_match:
            location = _clean(loc_match.group(1))

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
    text = re.sub(r'\s+', ' ', text)
    # HTML entity decode (basic)
    text = text.replace('&amp;', '&').replace('&#39;', "'").replace('&quot;', '"').replace('&nbsp;', ' ')
    # Strip Greenhouse badge suffixes (often concatenated without space, e.g. "Data ScientistNew")
    # Match capitalized badge words at end, preceded by lowercase letter (end of real word)
    text = re.sub(r'(?<=[a-z])(New|Featured|Recently Posted)$', '', text).strip()
    text = re.sub(r'\s+(New|Featured|Recently Posted)\s*$', '', text, flags=re.IGNORECASE).strip()
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
