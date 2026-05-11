from __future__ import annotations

import re
from typing import Any

import httpx

from app.logging_config import get_logger
from app.parsers.smartrecruiters import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest

log = get_logger("adapter.smartrecruiters")

# jobs.smartrecruiters.com/CompanyName or careers.smartrecruiters.com/CompanyName
_COMPANY_RE = re.compile(
    r"(?:jobs|careers)\.smartrecruiters\.com/([a-zA-Z0-9_-]+)",
    re.IGNORECASE,
)
_SUBDOMAIN_RE = re.compile(r"([a-zA-Z0-9_-]+)\.smartrecruiters\.com", re.IGNORECASE)


def _parse_company(url: str) -> str | None:
    m = _COMPANY_RE.search(url)
    if m:
        return m.group(1)
    # company.smartrecruiters.com subdomain form
    m2 = _SUBDOMAIN_RE.search(url)
    if m2 and m2.group(1) not in ("jobs", "careers", "api", "www"):
        return m2.group(1)
    return None


def _normalize_sr_jobs(data: dict, company_name: str | None) -> list[dict[str, Any]]:
    jobs = []
    for item in data.get("content", []):
        title = item.get("name", "")
        if not title:
            continue
        job_url = item.get("ref") or item.get("url")
        location_obj = item.get("location", {})
        if isinstance(location_obj, dict):
            city = location_obj.get("city", "")
            country = location_obj.get("country", "")
            location = ", ".join(p for p in [city, country] if p) or None
        else:
            location = str(location_obj) if location_obj else None
        department_obj = item.get("department", {})
        department = department_obj.get("label") if isinstance(department_obj, dict) else None
        jobs.append({
            "title": title,
            "company_name": company_name or "",
            "url": job_url,
            "location": location,
            "snippet": None,
            "department": department,
            "description": None,
            "source_site_family": "smartrecruiters",
            "source_site_variant": "api",
            "source_confidence": 0.98,
            "extraction_method": "api:smartrecruiters",
        })
    return jobs


@register_adapter
class SmartRecruitersAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="smartrecruiters",
        url_patterns=("smartrecruiters.com",),
        wait_selectors=("li.opening-job", ".details-title", "a.link--block"),
        supported_extraction_modes=("api", "dom_list", "json_ld"),
        fallback_order=10,
        api_capture_support=True,
        dom_markers=("opening-job", "details-title", "JobPosting"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)

    def api_url_for(self, listing_url: str) -> str | None:
        company = _parse_company(listing_url)
        return f"https://api.smartrecruiters.com/v1/companies/{company}/postings" if company else None

    def normalize_api_response(self, data, company_name):
        if not isinstance(data, dict) or "content" not in data:
            log.warning("SmartRecruiters API: unexpected response shape — %s", type(data).__name__)
            return []
        return _normalize_sr_jobs(data, company_name)

    async def fetch_api_jobs(
        self,
        url: str,
        company_name: str | None,
        request_id: str,
    ) -> list[dict[str, Any]] | None:
        api_url = self.api_url_for(url)
        if not api_url:
            log.debug("Could not parse SmartRecruiters company from %s [%s]", url, request_id)
            return None

        log.debug("SmartRecruiters API fetch: %s [%s]", api_url, request_id)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(api_url, headers={"User-Agent": "craftable-scraper/1.0"})
            if resp.status_code != 200:
                log.warning("SmartRecruiters API returned %d for %s [%s]", resp.status_code, api_url, request_id)
                return None
            data = resp.json()
        except Exception as exc:
            log.warning("SmartRecruiters API error for %s: %s [%s]", url, exc, request_id)
            return None

        jobs = self.normalize_api_response(data, company_name)
        log.info("SmartRecruiters API: %d jobs from %s [%s]", len(jobs), api_url, request_id)
        return jobs
