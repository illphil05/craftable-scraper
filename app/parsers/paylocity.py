"""Paylocity ATS parser.

URL pattern: recruiting.paylocity.com/Recruiting/Jobs/...
Job data is hydrated as JSON inside the rendered HTML. We extract each job
block by anchoring on `"JobId":<int>` and scanning a window of nearby chars
for the other fields (JobTitle, City, State, HiringDepartment).
"""
import re
from urllib.parse import urljoin


# Window (chars) to search around each JobId for the other fields.
# Job objects in the embedded JSON are typically ~500-1500 chars.
_WINDOW = 2000

_JOB_DETAIL_BASE = "https://recruiting.paylocity.com/Recruiting/Jobs/Details/"


def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    for m in re.finditer(r'"JobId"\s*:\s*(\d+)', html, re.IGNORECASE):
        job_id = m.group(1)
        # Fields for this job appear AFTER JobId in the JSON object;
        # don't peek backward or we'll grab the previous job's City/State.
        start = m.end()
        end = min(len(html), start + _WINDOW)
        window = html[start:end]

        title = _find(window, r'"JobTitle"\s*:\s*"([^"]+)"')
        if not title:
            continue

        city = _find(window, r'"City"\s*:\s*"([^"]+)"')
        state = _find(window, r'"State(?:Name)?"\s*:\s*"([^"]+)"')
        department = _find(window, r'"HiringDepartment"\s*:\s*"([^"]+)"')

        location = _build_location(city, state)
        job_url = f"{_JOB_DETAIL_BASE}{job_id}"

        _add(jobs, seen, title, job_url, location, department, company_name)

    return jobs


def _find(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None
    val = m.group(1).strip()
    return val or None


def _build_location(city: str | None, state: str | None) -> str | None:
    if city and state:
        return f"{city}, {state}"
    if city:
        return city
    if state:
        return state
    return None


def _clean(html_fragment: str) -> str:
    text = re.sub(r'<[^>]+>', '', html_fragment).strip()
    return re.sub(r'\s+', ' ', text)


def _add(
    jobs: list,
    seen: set,
    title: str,
    href: str | None,
    location: str | None,
    department: str | None,
    company_name: str | None,
):
    title = _clean(title)
    if not title or len(title) < 4 or len(title) > 150:
        return
    key = (title.lower(), (location or "").lower())
    if key in seen:
        return
    seen.add(key)
    jobs.append({
        "title": title,
        "company_name": company_name or "",
        "url": href,
        "location": location,
        "snippet": None,
        "department": department,
    })
