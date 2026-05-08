from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.logging_config import get_logger
from app.parsers.greenhouse import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest

log = get_logger("adapter.greenhouse")

_BOARD_TOKEN_RE = re.compile(
    r"greenhouse\.io/(?:embed/job_board\?for=|)([a-zA-Z0-9_-]+)",
    re.IGNORECASE,
)


def _parse_board_token(url: str) -> str | None:
    m = _BOARD_TOKEN_RE.search(url)
    return m.group(1) if m else None


def _normalize_greenhouse_jobs(data: dict, company_name: str | None) -> list[dict[str, Any]]:
    jobs = []
    for item in data.get("jobs", []):
        title = item.get("title", "")
        if not title:
            continue
        job_url = item.get("absolute_url") or item.get("url")
        location_obj = item.get("location", {})
        location = location_obj.get("name") if isinstance(location_obj, dict) else None
        offices = item.get("offices") or []
        if not location and offices:
            first_office = offices[0] if isinstance(offices[0], dict) else {}
            location = first_office.get("name")
        departments = item.get("departments") or []
        department = None
        if departments and isinstance(departments[0], dict):
            department = departments[0].get("name")
        # Full description is inside content field
        description = item.get("content")
        jobs.append({
            "title": title,
            "company_name": company_name or "",
            "url": job_url,
            "location": location,
            "snippet": None,
            "department": department,
            "description": description,
            "source_site_family": "greenhouse",
            "source_site_variant": "api",
            "source_confidence": 0.98,
            "extraction_method": "api:greenhouse",
        })
    return jobs


@register_adapter
class GreenhouseAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="greenhouse",
        url_patterns=("greenhouse.io",),
        wait_selectors=(".job-post", ".opening", "tr.job-post"),
        supported_extraction_modes=("api", "dom_list"),
        pagination_support=False,
        fallback_order=10,
        api_capture_support=True,
        dom_markers=("job-post", "opening", "/jobs/"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)

    async def fetch_api_jobs(
        self,
        url: str,
        company_name: str | None,
        request_id: str,
    ) -> list[dict[str, Any]] | None:
        board_token = _parse_board_token(url)
        if not board_token:
            log.debug("Could not parse Greenhouse board token from %s [%s]", url, request_id)
            return None

        api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
        log.debug("Greenhouse API fetch: %s [%s]", api_url, request_id)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(api_url, headers={"User-Agent": "craftable-scraper/1.0"})
            if resp.status_code != 200:
                log.warning("Greenhouse API returned %d for %s [%s]", resp.status_code, api_url, request_id)
                return None
            data = resp.json()
        except Exception as exc:
            log.warning("Greenhouse API error for %s: %s [%s]", url, exc, request_id)
            return None

        jobs = _normalize_greenhouse_jobs(data, company_name)
        log.info("Greenhouse API: %d jobs from %s [%s]", len(jobs), board_token, request_id)
        return jobs
