from __future__ import annotations

import asyncio

from app.logging_config import get_logger
from app.site_adapters.base import SiteAdapter

log = get_logger("botasaurus_scraper")


def _sync_botasaurus_get(url: str) -> str:
    """Fetch *url* with botasaurus Driver and return rendered HTML.

    Runs synchronously — call via asyncio.to_thread() from async code.
    Uses google_get() which routes the request through Google referrer
    to bypass Cloudflare challenges.
    """
    from botasaurus.browser import Driver

    driver = Driver(headless=True, block_images=True)
    try:
        driver.google_get(url, bypass_cloudflare=True)
        return driver.page_html
    finally:
        driver.close()


async def botasaurus_scrape(
    url: str,
    adapter: SiteAdapter,
    company_name: str | None,
    request_id: str,
) -> dict:
    """Async botasaurus fallback — runs sync driver in thread, parses with existing adapter."""
    log.info("Trying botasaurus fallback for '%s' [%s]", url, request_id)
    html = await asyncio.to_thread(_sync_botasaurus_get, url)
    jobs = adapter.parse_jobs(html, url, company_name, match_confidence=0.7)
    log.info(
        "Botasaurus fallback parsed %d jobs from '%s' [%s]",
        len(jobs), url, request_id,
    )
    return {
        "jobs": jobs,
        "company_name": jobs[0]["company_name"] if jobs and jobs[0].get("company_name") else (company_name or ""),
        "url": url,
        "method": f"botasaurus:{adapter.manifest.family}",
        "adapter_family": adapter.manifest.family,
        "adapter_variant": adapter.manifest.variant,
        "jobs_count": len(jobs),
        "error": None,
    }
