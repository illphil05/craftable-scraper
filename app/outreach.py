"""Outreach import helper — builds payloads and pushes to the outreach import endpoint.

Environment variables (read at call time):
  PUSH_TO_OUTREACH              - Set to "1", "true", or "yes" to enable scheduled push.
  PUSH_MANUAL_SAVES_TO_OUTREACH - Set to "1", "true", or "yes" to enable manual-save push.
  OUTREACH_IMPORT_URL           - Full URL of the outreach import endpoint.
  OUTREACH_API_KEY              - Bearer key; falls back to SCRAPER_API_KEY if unset or empty.
"""
from __future__ import annotations

import os

import httpx

from app.logging_config import get_logger

log = get_logger("outreach")


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


def build_outreach_import_payload(company: dict, careers_url: str, jobs: list[dict]) -> dict:
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
    return {
        "company_id": company.get("id"),
        "jobs": payload_jobs,
        "source": "craftable_scraper",
        "search_term": "scheduled_careers_sweep",
        "region": company.get("region") or "",
        "careers_url": careers_url,
    }


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
