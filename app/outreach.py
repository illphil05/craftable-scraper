"""Outreach import helper — builds payloads and pushes to the outreach import endpoint.

Environment variables (read at call time):
  PUSH_TO_OUTREACH       - Set to "1", "true", or "yes" to enable push.
  OUTREACH_IMPORT_URL    - Full URL of the outreach import endpoint.
  OUTREACH_API_KEY       - Bearer key; falls back to SCRAPER_API_KEY if unset or empty.
"""
from __future__ import annotations

import os

import httpx

from app.logging_config import get_logger

log = get_logger("outreach")


def env_truthy(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes"}


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
        "jobs": payload_jobs,
        "source": "craftable_scraper",
        "search_term": "scheduled_careers_sweep",
        "region": company.get("region") or "",
        "careers_url": careers_url,
    }


async def push_to_outreach(payload: dict, *, enabled_env: str = "PUSH_TO_OUTREACH") -> dict:
    if not env_truthy(enabled_env):
        return {"ok": False, "skipped": True}

    outreach_url = os.environ.get("OUTREACH_IMPORT_URL", "").strip()
    api_key = (os.environ.get("OUTREACH_API_KEY") or os.environ.get("SCRAPER_API_KEY", "")).strip()

    if not outreach_url:
        log.warning("Outreach push enabled but OUTREACH_IMPORT_URL is not set")
        return {"ok": False, "skipped": False}
    if not api_key:
        log.warning("Outreach push enabled but OUTREACH_API_KEY is not set")
        return {"ok": False, "skipped": False}
    if not payload.get("jobs"):
        return {"ok": False, "skipped": True}

    company_name = (payload["jobs"][0].get("company_name") or "") if payload.get("jobs") else ""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                outreach_url,
                json=payload,
                headers={"X-API-Key": api_key},
            )
        if response.status_code >= 400:
            log.error(
                "Outreach import failed for '%s': HTTP %d %s",
                company_name, response.status_code, response.text[:300],
            )
            return {"ok": False, "skipped": False}
        log.info("Outreach import pushed for '%s': %s", company_name, response.text[:300])
        return {"ok": True, "skipped": False}
    except Exception as exc:
        log.error("Outreach import error for '%s': %s", company_name, exc)
        return {"ok": False, "skipped": False}
