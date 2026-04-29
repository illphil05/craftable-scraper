"""Core scraper — uses Playwright to render JS, then passes HTML to ATS parsers.

Improvements over v1:
 - Uses the plugin registry for parser/selector lookup (no hardcoded lists).
 - Retry logic with exponential back-off (item 8).
 - asyncio.Semaphore caps concurrent browser instances (item 3).
 - Generic deep-scrape: any parser that exports `parse_detail` is used (item 7).
 - Structured logging throughout (item 11).
 - SSRF protection is validated by the caller (main.py) before reaching here.
"""
from __future__ import annotations

import asyncio
import random

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from app.logging_config import get_logger
from app.site_adapters import get_adapter
from app.botasaurus_scraper import botasaurus_scrape

log = get_logger("scraper")

# Maximum simultaneous Playwright browser instances.
_MAX_CONCURRENT = int(__import__("os").environ.get("MAX_CONCURRENT_SCRAPERS", "3"))
_BROWSER_SEM = asyncio.Semaphore(_MAX_CONCURRENT)

DEEP_SCRAPE_LIMIT = 50
DEEP_PAGE_TIMEOUT = 15_000

# Retry configuration
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0   # seconds
_RETRY_MAX_DELAY = 8.0

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


async def _wait_for_any_selector(page, selectors: list[str], *, timeout: int = 8_000) -> bool:
    """Wait for the first selector in *selectors* that attaches to the DOM."""
    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=timeout, state="attached")
            return True
        except Exception:
            continue
    return False


def _combined_wait_selectors(*selector_lists: list[str]) -> list[str]:
    combined: list[str] = []
    seen: set[str] = set()
    for selectors in selector_lists:
        for selector in selectors:
            if selector in seen:
                continue
            seen.add(selector)
            combined.append(selector)
    return combined


async def scrape_url(
    url: str,
    company_name: str | None = None,
    timeout: int = 30_000,
    *,
    debug: bool = False,
    deep: bool = False,
    request_id: str = "",
) -> dict:
    """Scrape *url* with Playwright and return parsed job listings.

    Retries up to _MAX_RETRIES times with exponential back-off on transient
    failures.  Each retry rotates the User-Agent string.
    """
    adapter = get_adapter(url)
    parser_name = adapter.manifest.family

    last_error: str | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            result = await _scrape_attempt(
                url=url,
                company_name=company_name,
                timeout=timeout,
                debug=debug,
                deep=deep,
                adapter=adapter,
                parser_name=parser_name,
                user_agent=_USER_AGENTS[(attempt - 1) % len(_USER_AGENTS)],
                request_id=request_id,
            )
            if attempt > 1:
                log.info("'%s' scrape succeeded on attempt %d [%s]", url, attempt, request_id)
            return result
        except Exception as exc:
            last_error = str(exc)
            error_type = "timeout" if isinstance(exc, PlaywrightTimeout) else "error"
            log.warning(
                "Scrape attempt %d/%d %s for '%s': %s [%s]",
                attempt, _MAX_RETRIES, error_type, url, last_error, request_id,
            )
            if attempt < _MAX_RETRIES:
                delay = min(_RETRY_BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 0.5), _RETRY_MAX_DELAY)
                log.debug("Retrying in %.1fs [%s]", delay, request_id)
                await asyncio.sleep(delay)

    log.error("All %d Playwright attempts failed for '%s': %s [%s]", _MAX_RETRIES, url, last_error, request_id)

    try:
        return await botasaurus_scrape(url, adapter, company_name, request_id)
    except Exception as bota_exc:
        log.error("Botasaurus fallback also failed for '%s': %s [%s]", url, bota_exc, request_id)
        last_error = str(bota_exc)

    return {
        "jobs": [],
        "company_name": company_name or "",
        "url": url,
        "method": f"botasaurus:{adapter.manifest.family}",
        "adapter_family": adapter.manifest.family,
        "adapter_variant": adapter.manifest.variant,
        "jobs_count": 0,
        "error": last_error,
        "error_type": "parse_failure",
    }


async def _scrape_attempt(
    *,
    url: str,
    company_name: str | None,
    timeout: int,
    debug: bool,
    deep: bool,
    adapter,
    parser_name: str,
    user_agent: str,
    request_id: str,
) -> dict:
    """Single attempt to scrape *url*.  Raises on any failure so the caller
    can retry."""
    selectors = list(adapter.manifest.wait_selectors)

    async with _BROWSER_SEM:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1366, "height": 768},
            )
            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page_context = await adapter.prepare_page(page, request_id)

            # Navigate — fall back to domcontentloaded if networkidle times out
            try:
                await page.goto(url, wait_until="networkidle", timeout=timeout)
            except PlaywrightTimeout:
                log.debug("networkidle timeout, falling back to domcontentloaded [%s]", request_id)
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

            # Wait for ATS-specific selector
            await _wait_for_any_selector(page, selectors)

            # Scroll to trigger lazy-loaded content
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1_500)
                await page.evaluate("window.scrollTo(0, 0)")
            except Exception as exc:
                log.debug("Scroll error (non-fatal): %s [%s]", exc, request_id)

            await page.wait_for_timeout(2_000)
            initial_html = await page.content()
            initial_finalized_html = await adapter.finalize_html(page, initial_html, page_context, request_id)
            resolved_adapter = get_adapter(
                url,
                html=initial_finalized_html,
                response_urls=page_context.get("captured_response_urls", []),
            )
            resolved_selectors = _combined_wait_selectors(
                selectors,
                list(resolved_adapter.manifest.wait_selectors),
            )
            await _wait_for_any_selector(page, resolved_selectors)
            await page.wait_for_timeout(500)
            resolved_html = await page.content()
            adapter = resolved_adapter
            parser_name = adapter.manifest.family
            final_html = await adapter.finalize_html(page, resolved_html, page_context, request_id)
            jobs = adapter.parse_jobs(
                final_html,
                url,
                company_name,
                match_confidence=adapter.match_confidence(
                    url,
                    html=final_html,
                    response_urls=page_context.get("captured_response_urls", []),
                ),
            )
            log.info("Parsed %d jobs from '%s' using %s [%s]", len(jobs), url, parser_name, request_id)

            # ── Tier 2: deep scrape detail pages ────────────────────────────
            if deep and jobs and adapter.manifest.detail_page_support:
                detail_limit = min(DEEP_SCRAPE_LIMIT, adapter.detail_limit)
                log.info("Deep scraping up to %d detail pages [%s]", detail_limit, request_id)
                jobs = await adapter.enrich_jobs(
                    page,
                    jobs,
                    request_id,
                    detail_limit=detail_limit,
                    detail_timeout_ms=DEEP_PAGE_TIMEOUT,
                )

            await browser.close()

    result: dict = {
        "jobs": jobs,
        "company_name": jobs[0]["company_name"] if jobs and jobs[0].get("company_name") else (company_name or ""),
        "url": url,
        "method": f"playwright:{parser_name}",
        "adapter_family": adapter.manifest.family,
        "adapter_variant": adapter.manifest.variant,
        "jobs_count": len(jobs),
        "error": None,
    }
    if debug:
        result["html_sample"] = final_html[:60_000]
        result["html_size"] = len(final_html)
        if page_context.get("captured_response_urls"):
            result["captured_response_urls"] = page_context["captured_response_urls"]
            result["captured_response_count"] = len(page_context.get("captured_response_urls", []))
    return result
