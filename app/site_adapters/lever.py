from __future__ import annotations

import re
from typing import Any

import httpx

from app.logging_config import get_logger
from app.parsers.lever import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest

log = get_logger("adapter.lever")

# e.g. jobs.lever.co/acme or jobs.lever.co/acme/
_COMPANY_RE = re.compile(r"jobs\.lever\.co/([a-zA-Z0-9_-]+)", re.IGNORECASE)


def _parse_company(url: str) -> str | None:
    m = _COMPANY_RE.search(url)
    return m.group(1) if m else None


def _normalize_lever_jobs(postings: list[dict], company_name: str | None) -> list[dict[str, Any]]:
    jobs = []
    for item in postings:
        title = item.get("text", "")
        if not title:
            continue
        job_url = item.get("hostedUrl") or item.get("url")
        categories = item.get("categories", {})
        location = categories.get("location") or categories.get("allLocations", [None])[0] if isinstance(categories, dict) else None
        if isinstance(location, list):
            location = location[0] if location else None
        department = categories.get("department") if isinstance(categories, dict) else None
        description_html = None
        if item.get("descriptionBody"):
            description_html = item["descriptionBody"]
        elif item.get("description"):
            description_html = item["description"]
        jobs.append({
            "title": title,
            "company_name": company_name or "",
            "url": job_url,
            "location": location,
            "snippet": None,
            "department": department,
            "description": description_html,
            "source_site_family": "lever",
            "source_site_variant": "api",
            "source_confidence": 0.98,
            "extraction_method": "api:lever",
        })
    return jobs


@register_adapter
class LeverAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="lever",
        url_patterns=("lever.co",),
        wait_selectors=(".posting-title", ".posting"),
        supported_extraction_modes=("api", "dom_list"),
        fallback_order=10,
        api_capture_support=True,
        dom_markers=("posting-title", "posting-name", "jobs.lever.co"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)

    async def fetch_api_jobs(
        self,
        url: str,
        company_name: str | None,
        request_id: str,
    ) -> list[dict[str, Any]] | None:
        company = _parse_company(url)
        if not company:
            log.debug("Could not parse Lever company from %s [%s]", url, request_id)
            return None

        api_url = f"https://api.lever.co/v0/postings/{company}?mode=json"
        log.debug("Lever API fetch: %s [%s]", api_url, request_id)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(api_url, headers={"User-Agent": "craftable-scraper/1.0"})
            if resp.status_code != 200:
                log.warning("Lever API returned %d for %s [%s]", resp.status_code, api_url, request_id)
                return None
            data = resp.json()
        except Exception as exc:
            log.warning("Lever API error for %s: %s [%s]", url, exc, request_id)
            return None

        if not isinstance(data, list):
            log.warning("Lever API returned unexpected shape for %s [%s]", url, request_id)
            return None

        jobs = _normalize_lever_jobs(data, company_name)
        log.info("Lever API: %d jobs from %s [%s]", len(jobs), company, request_id)
        return jobs
