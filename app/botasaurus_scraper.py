import asyncio

from app.logging_config import get_logger
from app.site_adapters.base import SiteAdapter

log = get_logger("botasaurus_scraper")

_MATCH_CONFIDENCE = 0.7


def _sync_botasaurus_get(url: str) -> str:
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
    timeout: float = 60.0,
) -> dict:
    log.info("Trying botasaurus fallback for '%s' [%s]", url, request_id)
    html = await asyncio.wait_for(asyncio.to_thread(_sync_botasaurus_get, url), timeout=timeout)
    jobs = adapter.parse_jobs(html, url, company_name, match_confidence=_MATCH_CONFIDENCE)
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
