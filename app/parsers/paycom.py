import json
import re

from bs4 import BeautifulSoup

from app.parsers import register_parser

_PORTAL_KEY_RE = re.compile(r"^[A-F0-9]{32}$", re.IGNORECASE)


@register_parser("paycomonline.net", [])
def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    html = html.lstrip("\ufeff")
    if not html or html[0] not in ("{", "["):
        return []

    try:
        data = json.loads(html)
    except (json.JSONDecodeError, ValueError):
        return []

    jobs_raw = data.get("jobs", [])
    portal_key = data.get("portal_key", "")
    if not _PORTAL_KEY_RE.match(portal_key):
        portal_key = ""
    name = company_name or data.get("company_name") or ""

    results = []
    seen = set()

    for job in jobs_raw:
        title = (job.get("jobTitle") or "").strip()
        if not title:
            continue

        job_id = job.get("jobId", "")
        job_url = (
            f"https://www.paycomonline.net/v4/ats/web.php/portal/{portal_key}"
            f"/career-page#/jobs/{job_id}"
        )

        key = (title.lower(), job_url)
        if key in seen:
            continue
        seen.add(key)

        location = job.get("city") or job.get("locations") or None

        snippet_html = job.get("description_full") or job.get("description") or ""
        if snippet_html:
            text = BeautifulSoup(snippet_html, "lxml").get_text(separator=" ", strip=True)
            snippet = text[:500] if text else None
        else:
            snippet = None

        department = job.get("jobCategory") or None

        results.append({
            "title": title,
            "company_name": name,
            "url": job_url,
            "location": location,
            "snippet": snippet,
            "department": department,
        })

    return results
