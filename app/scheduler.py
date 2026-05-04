"""Background scheduler — re-scrapes all companies on a configurable interval.

Environment variables:
  SCRAPE_INTERVAL_HOURS  - Hours between full re-scrape cycles (default: 24).
                           Set to 0 to disable the scheduler.
"""
from __future__ import annotations

import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import httpx

from app.logging_config import get_logger
from app import db
from app.intelligence.enricher import run_enrichment_batch
from app.scraper import scrape_url

log = get_logger("scheduler")

_scheduler: AsyncIOScheduler | None = None
_INTERVAL_HOURS = int(os.environ.get("SCRAPE_INTERVAL_HOURS", "24"))
_PUSH_TO_OUTREACH = os.environ.get("PUSH_TO_OUTREACH", "false").lower() in {"1", "true", "yes"}
_OUTREACH_IMPORT_URL = os.environ.get("OUTREACH_IMPORT_URL", "").strip()
_OUTREACH_API_KEY = os.environ.get("OUTREACH_API_KEY", os.environ.get("SCRAPER_API_KEY", "")).strip()


async def _push_to_outreach(company: dict, careers_url: str, jobs: list[dict]) -> None:
    if not _PUSH_TO_OUTREACH:
        return
    if not _OUTREACH_IMPORT_URL:
        log.warning("Outreach push enabled but OUTREACH_IMPORT_URL is not set")
        return
    if not _OUTREACH_API_KEY:
        log.warning("Outreach push enabled but OUTREACH_API_KEY is not set")
        return
    if not jobs:
        return

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

    payload = {
        "jobs": payload_jobs,
        "source": "craftable_scraper",
        "search_term": "scheduled_careers_sweep",
        "region": company.get("region") or "",
        "careers_url": careers_url,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _OUTREACH_IMPORT_URL,
                json=payload,
                headers={"X-API-Key": _OUTREACH_API_KEY},
            )
        if response.status_code >= 400:
            log.error("Outreach import failed for '%s': HTTP %d %s", company.get("name"), response.status_code, response.text[:300])
            return
        log.info("Outreach import pushed for '%s': %s", company.get("name"), response.text[:300])
    except Exception as exc:
        log.error("Outreach import error for '%s': %s", company.get("name"), exc)


async def _run_scheduled_scrape() -> None:
    """Re-scrape every company that has a careers_url set."""
    result = await db.list_companies(limit=500)
    companies = [c for c in result["companies"] if c.get("careers_url")]
    if not companies:
        log.info("Scheduled scrape: no companies with careers_url, skipping")
        return

    log.info("Scheduled scrape starting for %d companies", len(companies))
    success = fail = 0
    for company in companies:
        url = company["careers_url"]
        try:
            res = await scrape_url(url, company_name=company["name"], request_id="scheduled")
            scrape_id = await db.save_scrape(
                company_id=company["id"],
                url=url,
                parser_used=res["method"],
                jobs_found=res["jobs_count"],
                elapsed_ms=res.get("elapsed_ms", 0),
                error=res.get("error"),
                html_size=res.get("html_size"),
                deep=False,
            )
            if res["jobs"]:
                await db.save_jobs(company["id"], scrape_id, res["jobs"])
                await _push_to_outreach(company, url, res["jobs"])
            success += 1
        except Exception as exc:
            log.error("Scheduled scrape failed for '%s': %s", url, exc)
            fail += 1

    log.info("Scheduled scrape complete: %d succeeded, %d failed", success, fail)


def start_scheduler() -> None:
    global _scheduler
    if _INTERVAL_HOURS <= 0:
        log.info("Scheduler disabled (SCRAPE_INTERVAL_HOURS=0)")
        return

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _run_scheduled_scrape,
        trigger=IntervalTrigger(hours=_INTERVAL_HOURS),
        id="scheduled_scrape",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.add_job(
        run_enrichment_batch,
        trigger=IntervalTrigger(minutes=5),
        id="enrichment_batch",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    log.info("Scheduler started — re-scraping every %dh, enrichment every 5m", _INTERVAL_HOURS)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("Scheduler stopped")
    _scheduler = None
