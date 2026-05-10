"""Background scheduler — re-scrapes all companies on a configurable interval.

Environment variables:
  SCRAPE_INTERVAL_HOURS  - Hours between full re-scrape cycles (default: 24).
                           Set to 0 to disable the scheduler.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.logging_config import get_logger
from app import db
from app.intelligence.enricher import run_enrichment_batch
from app.outreach import build_outreach_import_payload, push_to_outreach, fetch_outreach_config
from app.scraper import scrape_url

log = get_logger("scheduler")

_scheduler: AsyncIOScheduler | None = None
_INTERVAL_HOURS = int(os.environ.get("SCRAPE_INTERVAL_HOURS", "24"))

_PAGE_SIZE = 500


async def _run_scheduled_scrape() -> None:
    """Re-scrape every company that has a careers_url set."""
    # Pull latest config from outreach before starting — failure falls back to empty
    outreach_cfg = await fetch_outreach_config()
    extra_ignored_patterns = outreach_cfg.get("ignored_title_patterns") or []
    blocked_domains = set(outreach_cfg.get("blocked_domains") or [])

    page_num = 1
    companies = []
    while True:
        result = await db.list_companies(page=page_num, limit=_PAGE_SIZE)
        batch = [c for c in result["companies"] if c.get("careers_url")]
        companies.extend(batch)
        if len(result["companies"]) < _PAGE_SIZE:
            break
        page_num += 1

    if not companies:
        log.info("Scheduled scrape: no companies with careers_url, skipping")
        return

    log.info(
        "Scheduled scrape starting for %d companies (%d extra ignored patterns, %d blocked domains)",
        len(companies), len(extra_ignored_patterns), len(blocked_domains),
    )
    success = fail = 0
    total_ignored = 0
    total_blocked = 0
    for company in companies:
        url = company["careers_url"]

        # Skip companies whose careers page is on a blocked domain
        try:
            domain = urlparse(url).hostname or ""
        except Exception:
            domain = ""
        if domain and domain in blocked_domains:
            log.debug("Skipping blocked domain '%s' for company '%s'", domain, company.get("name"))
            total_blocked += 1
            continue

        try:
            res = await scrape_url(
                url,
                company_name=company["name"],
                request_id="scheduled",
                ignored_title_patterns=extra_ignored_patterns,
            )
            scrape_id = await db.save_scrape(
                company_id=company["id"],
                url=url,
                parser_used=res["method"],
                adapter_family=res.get("adapter_family"),
                adapter_variant=res.get("adapter_variant"),
                jobs_found=res["jobs_count"],
                elapsed_ms=res.get("elapsed_ms", 0),
                error=res.get("error"),
                error_code=res.get("error_code"),
                html_size=res.get("html_size"),
                artifact_refs=res.get("artifact_refs") or {},
                deep=False,
            )
            run_ignored = res.get("ignored_count", 0)
            total_ignored += run_ignored
            if res["jobs"]:
                await db.save_jobs(company["id"], scrape_id, res["jobs"])
                payload = build_outreach_import_payload(
                    company, url, res["jobs"],
                    ignored_count=run_ignored,
                    blocked_domain_count=0,
                )
                await push_to_outreach(payload)
            success += 1
        except Exception as exc:
            log.error("Scheduled scrape failed for '%s': %s", url, exc)
            fail += 1

    log.info(
        "Scheduled scrape complete: %d succeeded, %d failed, %d ignored titles, %d blocked domains",
        success, fail, total_ignored, total_blocked,
    )


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
