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
from app.parsers import get_parser, get_parser_name, get_wait_selectors

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
    parser = get_parser(url)
    parser_name = get_parser_name(url)
    is_ukg = "ultipro.com" in url.lower()

    # Discover whether this parser has a detail-page enrichment function (item 7)
    parse_detail_fn = getattr(parser, "__module__", None)
    if parse_detail_fn:
        import importlib
        mod = importlib.import_module(parse_detail_fn)
        parse_detail_fn = getattr(mod, "parse_detail", None)
    else:
        parse_detail_fn = None

    last_error: str | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            result = await _scrape_attempt(
                url=url,
                company_name=company_name,
                timeout=timeout,
                debug=debug,
                deep=deep,
                parser=parser,
                parser_name=parser_name,
                is_ukg=is_ukg,
                parse_detail_fn=parse_detail_fn,
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

    log.error("All %d scrape attempts failed for '%s': %s [%s]", _MAX_RETRIES, url, last_error, request_id)
    return {
        "jobs": [],
        "company_name": company_name or "",
        "url": url,
        "method": f"playwright:{parser_name}",
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
    parser,
    parser_name: str,
    is_ukg: bool,
    parse_detail_fn,
    user_agent: str,
    request_id: str,
) -> dict:
    """Single attempt to scrape *url*.  Raises on any failure so the caller
    can retry."""
    selectors = get_wait_selectors(url)

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

            # UKG: capture XHR/fetch responses before navigation
            ukg_api_responses: list[str] = []
            ukg_api_urls: list[str] = []
            if is_ukg:
                async def capture_response(response):
                    try:
                        resp_url = response.url
                        ct = response.headers.get("content-type", "")
                        if any(ext in resp_url.lower() for ext in [".css", ".png", ".jpg", ".gif", ".svg", ".woff", ".ttf", ".ico"]):
                            return
                        if "json" in ct or "html" in ct or "xml" in ct or "text/plain" in ct:
                            body = await response.text()
                            if body and len(body) > 100:
                                ukg_api_responses.append(body)
                                ukg_api_urls.append(f"{response.status} {resp_url[:200]}")
                    except Exception as exc:
                        log.debug("UKG response capture error: %s [%s]", exc, request_id)

                page.on("response", capture_response)

            # Navigate — fall back to domcontentloaded if networkidle times out
            try:
                await page.goto(url, wait_until="networkidle", timeout=timeout)
            except PlaywrightTimeout:
                log.debug("networkidle timeout, falling back to domcontentloaded [%s]", request_id)
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

            # Wait for ATS-specific selector
            for sel in selectors:
                try:
                    await page.wait_for_selector(sel, timeout=8_000, state="attached")
                    break
                except Exception:
                    continue

            # Scroll to trigger lazy-loaded content
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1_500)
                await page.evaluate("window.scrollTo(0, 0)")
            except Exception as exc:
                log.debug("Scroll error (non-fatal): %s [%s]", exc, request_id)

            await page.wait_for_timeout(2_000)
            html = await page.content()

            # UKG: extract shadow DOM + append captured API responses
            if is_ukg:
                await page.wait_for_timeout(3_000)
                try:
                    shadow_html = await page.evaluate("""() => {
                        const parts = [];
                        function walk(root) {
                            root.querySelectorAll('*').forEach(el => {
                                if (el.shadowRoot) {
                                    parts.push(el.shadowRoot.innerHTML);
                                    walk(el.shadowRoot);
                                }
                            });
                        }
                        walk(document);
                        return parts.join('\\n');
                    }""")
                    if shadow_html and len(shadow_html) > 100:
                        html += "\n" + shadow_html
                except Exception as exc:
                    log.debug("Shadow DOM extraction error (non-fatal): %s [%s]", exc, request_id)
                for resp in ukg_api_responses:
                    html += "\n" + resp

            jobs = parser(html, url, company_name)
            log.info("Parsed %d jobs from '%s' using %s [%s]", len(jobs), url, parser_name, request_id)

            # ── Tier 2: deep scrape detail pages ────────────────────────────
            if deep and jobs and parse_detail_fn:
                log.info("Deep scraping up to %d detail pages [%s]", DEEP_SCRAPE_LIMIT, request_id)
                for job in jobs[:DEEP_SCRAPE_LIMIT]:
                    job_url = job.get("url")
                    if not job_url:
                        continue
                    try:
                        await page.goto(job_url, wait_until="domcontentloaded", timeout=DEEP_PAGE_TIMEOUT)
                        await page.wait_for_timeout(1_500)
                        detail_html = await page.content()
                        enrichment = parse_detail_fn(detail_html)
                        for key in ("description", "requirements", "full_address", "maps_url", "posted_date"):
                            if enrichment.get(key) is not None:
                                job[key] = enrichment[key]
                    except Exception as exc:
                        log.debug("Detail page error for '%s': %s [%s]", job_url, exc, request_id)

            await browser.close()

    return {
        "jobs": jobs,
        "company_name": jobs[0]["company_name"] if jobs and jobs[0].get("company_name") else (company_name or ""),
        "url": url,
        "method": f"playwright:{parser_name}",
        "jobs_count": len(jobs),
        "error": None,
        **({"html_sample": html[:60_000], "html_size": len(html), **({"ukg_api_urls": ukg_api_urls, "ukg_api_count": len(ukg_api_responses)} if is_ukg and ukg_api_urls else {})} if debug else {}),
    }
