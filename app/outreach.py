"""Outreach import helper — builds payloads and pushes to the outreach import endpoint.

Environment variables (read at call time):
  PUSH_TO_OUTREACH              - Set to "1", "true", or "yes" to enable scheduled push.
  PUSH_MANUAL_SAVES_TO_OUTREACH - Set to "1", "true", or "yes" to enable manual-save push.
  OUTREACH_IMPORT_URL           - Full URL of the outreach import endpoint.
  OUTREACH_API_KEY              - Bearer key; falls back to SCRAPER_API_KEY if unset or empty.
"""
from __future__ import annotations

import os
import time

import httpx

from app.logging_config import get_logger

log = get_logger("outreach")

# Config cache — refreshed at most every 5 minutes
_config_cache: dict | None = None
_config_cached_at: float = 0.0
_CONFIG_MAX_AGE = 300.0  # seconds


async def fetch_outreach_config() -> dict:
    """Pull ignored title patterns + blocked domains from outreach.

    Returns last known config on failure. Never raises.
    """
    global _config_cache, _config_cached_at

    if _config_cache is not None and (time.monotonic() - _config_cached_at) < _CONFIG_MAX_AGE:
        return _config_cache

    import_url = os.environ.get("OUTREACH_IMPORT_URL", "").strip()
    api_key = (os.environ.get("OUTREACH_API_KEY") or os.environ.get("SCRAPER_API_KEY", "")).strip()

    if not import_url or not api_key:
        return _config_cache or {}

    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(import_url)
    config_path = parsed.path.rstrip("/").removesuffix("/import") + "/config"
    config_url = urlunparse(parsed._replace(path=config_path, query="", fragment=""))

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(config_url, headers={"X-API-Key": api_key})
        if resp.status_code == 200:
            data = resp.json()
            _config_cache = data
            _config_cached_at = time.monotonic()
            log.debug(
                "Fetched outreach config: %d ignored patterns, %d blocked domains",
                len(data.get("ignored_title_patterns") or []),
                len(data.get("blocked_domains") or []),
            )
            return data
        log.warning("Outreach config fetch returned HTTP %d — using last known config", resp.status_code)
    except Exception as exc:
        log.warning("Outreach config fetch failed: %s — using last known config", exc)

    return _config_cache or {}


def env_truthy(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes"}


def outreach_config_status() -> dict:
    """Return current outreach config flags (no secret values)."""
    return {
        "push_to_outreach": env_truthy("PUSH_TO_OUTREACH"),
        "push_manual_saves_to_outreach": env_truthy("PUSH_MANUAL_SAVES_TO_OUTREACH"),
        "import_url_set": bool(os.environ.get("OUTREACH_IMPORT_URL", "").strip()),
        "api_key_set": bool(
            (os.environ.get("OUTREACH_API_KEY") or os.environ.get("SCRAPER_API_KEY", "")).strip()
        ),
    }


def build_outreach_import_payload(
    company: dict,
    careers_url: str,
    jobs: list[dict],
    *,
    ignored_count: int = 0,
    blocked_domain_count: int = 0,
    adapter_family: str | None = None,
    adapter_variant: str | None = None,
    parse_method: str | None = None,
    scrape_quality: dict | None = None,
) -> dict:
    payload_jobs = []
    for job in jobs:
        payload_jobs.append({
            **job,
            "company_name": job.get("company_name") or company.get("name"),
            "source": "craftable_scraper",
            "discovered_at": job.get("discovered_at") or job.get("first_seen") or None,
            "source_url": job.get("url"),
            "full_description": job.get("description"),
        })
    payload: dict = {
        "company_id": company.get("id"),
        "jobs": payload_jobs,
        "source": "craftable_scraper",
        "search_term": "scheduled_careers_sweep",
        "region": company.get("region") or "",
        "careers_url": careers_url,
        "ignored_count": ignored_count,
        "blocked_domain_count": blocked_domain_count,
    }
    # Source diagnostics and quality metadata — additive, omitted when not available
    if adapter_family:
        payload["adapter_family"] = adapter_family
    if adapter_variant:
        payload["adapter_variant"] = adapter_variant
    if parse_method:
        payload["parse_method"] = parse_method
    if scrape_quality:
        payload["scrape_quality"] = scrape_quality
    return payload


async def push_to_outreach(payload: dict, *, enabled_env: str = "PUSH_TO_OUTREACH") -> dict:
    careers_url = payload.get("careers_url", "")
    company_id = payload.get("company_id", "")
    jobs_count = len(payload.get("jobs") or [])
    company_name = (payload["jobs"][0].get("company_name") or "") if jobs_count else ""

    if not env_truthy(enabled_env):
        log.debug(
            "Outreach push skipped company_id=%s careers_url=%s jobs=%d enabled_env=%s",
            company_id, careers_url, jobs_count, enabled_env,
        )
        return {"ok": False, "skipped": True}

    outreach_url = os.environ.get("OUTREACH_IMPORT_URL", "").strip()
    api_key = (os.environ.get("OUTREACH_API_KEY") or os.environ.get("SCRAPER_API_KEY", "")).strip()

    if not outreach_url:
        log.warning(
            "Outreach push enabled but OUTREACH_IMPORT_URL is not set "
            "company_id=%s enabled_env=%s", company_id, enabled_env,
        )
        return {"ok": False, "skipped": False}
    if not api_key:
        log.warning(
            "Outreach push enabled but OUTREACH_API_KEY is not set "
            "company_id=%s enabled_env=%s", company_id, enabled_env,
        )
        return {"ok": False, "skipped": False}
    if not jobs_count:
        return {"ok": False, "skipped": True}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                outreach_url,
                json=payload,
                headers={"X-API-Key": api_key},
            )
        if response.status_code >= 400:
            log.error(
                "Outreach import failed company_id=%s company=%s careers_url=%s "
                "jobs=%d enabled_env=%s http_status=%d body=%s",
                company_id, company_name, careers_url, jobs_count, enabled_env,
                response.status_code, response.text[:300],
            )
            return {"ok": False, "skipped": False, "http_status": response.status_code}
        log.info(
            "Outreach import ok company_id=%s company=%s careers_url=%s "
            "jobs=%d enabled_env=%s http_status=%d",
            company_id, company_name, careers_url, jobs_count, enabled_env,
            response.status_code,
        )
        return {"ok": True, "skipped": False, "http_status": response.status_code}
    except Exception as exc:
        log.error(
            "Outreach import error company_id=%s company=%s careers_url=%s "
            "jobs=%d enabled_env=%s error=%s",
            company_id, company_name, careers_url, jobs_count, enabled_env, exc,
        )
        return {"ok": False, "skipped": False}
