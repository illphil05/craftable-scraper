from app.parsers.paycom import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest

API_BASE_URL = "https://portal-applicant-tracking.us-cent.paycomonline.net"

_API_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://www.paycomonline.net",
    "Referer": "https://www.paycomonline.net/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


@register_adapter
class PaycomAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="paycom",
        url_patterns=("paycomonline.net",),
        wait_selectors=(),
        supported_extraction_modes=("api_capture",),
        api_capture_support=True,
        detail_page_support=False,
        fallback_order=10,
        dom_markers=("paycomonline.net", "sessionJWT"),
        api_markers=("portal-applicant-tracking",),
        confidence_rules={"url_pattern": 0.97, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)

    async def finalize_html(self, page, html: str, page_context: dict, request_id: str) -> str:
        import re
        import json
        import asyncio
        import os
        import httpx

        page_url = page.url
        key_match = re.search(r"/portal/([A-F0-9]{32})/", page_url, re.IGNORECASE)
        if not key_match:
            return html
        portal_key = key_match.group(1).upper()

        jwt_match = re.search(r'"sessionJWT"\s*:\s*"([^"]+)"', html)
        if not jwt_match:
            raise ValueError(f"Paycom: could not find sessionJWT in page HTML for {page_url}")
        jwt = jwt_match.group(1)

        api_base_match = re.search(r'atsPortalMantleServiceUrl\\":\\"(https://[^\\]+)', html)
        if api_base_match:
            candidate = api_base_match.group(1).rstrip("/")
            api_base = candidate if "paycomonline.net" in candidate else API_BASE_URL
        else:
            api_base = API_BASE_URL

        auth_headers = {**_API_HEADERS, "Authorization": f"Bearer {jwt}"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                r = await client.get(f"{api_base}/api/ats/company-name", headers=auth_headers)
                r.raise_for_status()
                company_name = r.json().get("companyName", "")
            except Exception as exc:
                log.debug("Paycom company-name fetch failed: %s", exc)
                company_name = ""

            previews = []
            skip = 0
            batch = 100
            while True:
                payload = {
                    "skip": skip,
                    "take": batch,
                    "filtersForQuery": {
                        "distanceFrom": 0,
                        "workEnvironments": [],
                        "positionTypes": [],
                        "educationLevels": [],
                        "categories": [],
                        "travelTypes": [],
                        "shiftTypes": [],
                        "otherFilters": [],
                        "keywordSearchText": "",
                        "location": "",
                        "sortOption": "",
                    },
                }
                r = await client.post(
                    f"{api_base}/api/ats/job-posting-previews/search",
                    headers=auth_headers,
                    json=payload,
                )
                r.raise_for_status()
                data = r.json()
                batch_jobs = data.get("jobPostingPreviews", [])
                total = data.get("jobPostingPreviewsCount", 0)
                previews.extend(batch_jobs)
                skip += len(batch_jobs)
                if skip >= total or not batch_jobs or len(previews) > 10_000:
                    break

            try:
                detail_limit = int(os.environ.get("PAYCOM_DETAIL_LIMIT", "50"))
            except (ValueError, TypeError):
                detail_limit = 50
            try:
                detail_delay = float(os.environ.get("PAYCOM_DETAIL_DELAY", "0.2"))
            except (ValueError, TypeError):
                detail_delay = 0.2
            detail_delay = max(0.05, min(detail_delay, 5.0))
            capped = previews[:detail_limit]
            for i, job in enumerate(capped):
                job_id = job.get("jobId")
                if not job_id:
                    continue
                try:
                    dr = await client.get(
                        f"{api_base}/api/ats/job-postings/{job_id}", headers=auth_headers
                    )
                    if dr.status_code == 200:
                        detail = dr.json().get("jobPosting", {})
                        job["city"] = detail.get("city", "")
                        job["salaryRange"] = detail.get("salaryRange", "")
                        job["jobCategory"] = detail.get("jobCategory", "")
                        job["educationLevel"] = detail.get("educationLevel", "")
                        job["description_full"] = detail.get("description", "")
                        job["qualifications"] = detail.get("qualifications", "")
                except Exception as exc:
                    log.debug("Paycom detail fetch failed for job %s: %s", job_id, exc)
                if i < len(capped) - 1:
                    await asyncio.sleep(detail_delay)

        return json.dumps({"jobs": previews, "company_name": company_name, "portal_key": portal_key})
