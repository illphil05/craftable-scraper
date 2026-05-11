"""Core scraper — layered extraction pipeline.

Strategy order per request:
  1. API-first site adapter (fetch_api_jobs)
  2. Playwright site adapter
  3. Bright Data Web Unlocker REST fallback
  4. Dynamic parser over unlocked HTML
  5. Botasaurus fallback (for non-API-capture adapters)

Improvements over v1:
 - ExtractionResult TypedDict for structured pipeline results.
 - API-first path bypasses Playwright for known ATS REST endpoints.
 - Bright Data REST fallback for blocked/unknown domains.
 - Dynamic parser for parserless job URLs.
 - extraction_attempts list for structured diagnostics.
 - Retry logic with exponential back-off.
 - asyncio.Semaphore caps concurrent browser instances.
 - Generic deep-scrape: any parser that exports `parse_detail` is used.
 - SSRF protection is validated by the caller (main.py) before reaching here.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import re
import time
from typing import TypedDict
from urllib.parse import urlparse

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from app.logging_config import get_logger
from app.site_adapters import get_adapter
from app.botasaurus_scraper import botasaurus_scrape
from app.url_classifier import is_detail_page
from app.parsers.detail import extract_job_from_detail_page


def _brightdata_browser_ws() -> str | None:
    """Return BrightData Browser API websocket URL if configured."""
    return os.environ.get("BRIGHTDATA_BROWSER_WS") or None


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

# ── Error codes ───────────────────────────────────────────────────────────────
EC_IP_BLOCKED = "ip_blocked"
EC_URL_NOT_FOUND = "url_not_found"
EC_CAPTCHA = "captcha_detected"
EC_TIMEOUT = "timeout"
EC_PARSE_FAILURE = "parse_failure"
EC_NETWORK_ERROR = "network_error"

_NON_RETRYABLE = {EC_IP_BLOCKED, EC_URL_NOT_FOUND}
# Error codes that should trigger Bright Data fallback
_BRIGHTDATA_TRIGGER_CODES = {EC_IP_BLOCKED, EC_CAPTCHA, EC_TIMEOUT, EC_NETWORK_ERROR}

# ── Circuit breaker ───────────────────────────────────────────────────────────
_CB_TTL = float(os.environ.get("CB_TTL_SECONDS", "3600"))  # 1 hour default
_circuit_breaker: dict[str, tuple[str, float]] = {}


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _cb_check(url: str) -> tuple[bool, str]:
    """Return (blocked, error_code). True if the domain circuit is open."""
    d = _domain(url)
    entry = _circuit_breaker.get(d)
    if entry:
        ec, ts = entry
        if time.monotonic() - ts < _CB_TTL:
            return True, ec
        del _circuit_breaker[d]
    return False, ""


def _cb_trip(url: str, error_code: str) -> None:
    d = _domain(url)
    _circuit_breaker[d] = (error_code, time.monotonic())
    log.warning("Circuit breaker tripped for '%s': %s", d, error_code)


def _classify_error(exc: BaseException | None, html: str = "") -> str:
    """Map an exception (or 0-job HTML) to a structured error code."""
    if isinstance(exc, PlaywrightTimeout):
        return EC_TIMEOUT

    exc_str = str(exc) if exc else ""

    if "ERR_HTTP_RESPONSE_CODE_FAILURE" in exc_str:
        m = re.search(r"(\d{3})", exc_str)
        if m:
            status = int(m.group(1))
            if status == 404:
                return EC_URL_NOT_FOUND
            if status in (403, 429, 503):
                return EC_IP_BLOCKED
        return EC_NETWORK_ERROR

    if "net::" in exc_str or "connection" in exc_str.lower() or "unreachable" in exc_str.lower():
        return EC_NETWORK_ERROR

    if html:
        lower = html.lower()
        if len(html) < 800 and any(w in lower for w in ("blocked", "access denied", "403")):
            return EC_IP_BLOCKED
        if any(w in lower for w in ("captcha", "are you a robot", "cloudflare challenge", "security check")):
            return EC_CAPTCHA

    return EC_PARSE_FAILURE


_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


# ── ExtractionResult ──────────────────────────────────────────────────────────

class ExtractionResult(TypedDict, total=False):
    jobs: list[dict]
    html: str
    method: str
    adapter_family: str
    adapter_variant: str
    extraction_attempts: list[dict]
    error: str | None
    error_code: str | None


# ── Helpers ───────────────────────────────────────────────────────────────────

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


_BASELINE_IGNORED_TITLES: list[dict] = [
    {"title_pattern": "español", "match_type": "exact"},
    {"title_pattern": "francais", "match_type": "exact"},
    {"title_pattern": "français", "match_type": "exact"},
    {"title_pattern": "deutsch", "match_type": "exact"},
    {"title_pattern": "save", "match_type": "exact"},
    {"title_pattern": "apply", "match_type": "exact"},
    {"title_pattern": "close", "match_type": "exact"},
    {"title_pattern": "sign in", "match_type": "exact"},
    {"title_pattern": "log in", "match_type": "exact"},
    {"title_pattern": r"^.{1,2}$", "match_type": "regex"},
]


def _is_ignored_title(title: str, patterns: list[dict]) -> bool:
    """Return True if job title matches any ignored-title pattern."""
    normalized = (title or "").strip().lower()
    if not normalized:
        return False
    for p in patterns:
        pat = p.get("title_pattern", "")
        match_type = p.get("match_type", "exact")
        if match_type == "exact" and normalized == pat:
            return True
        if match_type == "contains" and pat in normalized:
            return True
        if match_type == "regex":
            try:
                if re.search(pat, normalized, re.IGNORECASE):
                    return True
            except re.error:
                pass
    return False


# ── Bright Data fallback ──────────────────────────────────────────────────────

async def _brightdata_api_fallback(
    url: str,
    company_name: str | None,
    adapter,
    request_id: str,
) -> dict | None:
    """Proxy the adapter's ATS REST API call through Bright Data Web Unlocker.

    Called when _api_first_attempt() returned None (direct API unreachable).
    Returns a scrape result dict on success, or None if not applicable.
    """
    from app import brightdata as bd

    if not bd.is_configured():
        return None
    api_url = adapter.api_url_for(url)
    if not api_url:
        return None

    log.debug("BrightData API proxy: %s [%s]", api_url, request_id)
    try:
        result = await bd.unlock_url(api_url)
        data = json.loads(result["body"])
    except Exception as exc:
        log.warning("BrightData API proxy failed for %s: %s [%s]", api_url, exc, request_id)
        return None

    jobs = adapter.normalize_api_response(data, company_name)
    log.info("BrightData API proxy: %d jobs from %s [%s]", len(jobs), api_url, request_id)

    family = adapter.manifest.family
    return {
        "jobs": jobs,
        "company_name": jobs[0].get("company_name", company_name or "") if jobs else (company_name or ""),
        "url": url,
        "method": f"brightdata:api:{family}",
        "adapter_family": family,
        "adapter_variant": "brightdata_api",
        "jobs_count": len(jobs),
        # Treat zero jobs as a trusted "no openings" signal, same as _api_first_attempt.
        "error": None,
        "error_code": None,
        "extraction_attempts": [
            {"method": f"brightdata:api:{family}", "api_url": api_url, "jobs": len(jobs)},
        ],
    }


async def _brightdata_fallback(
    url: str,
    company_name: str | None,
    adapter,
    request_id: str,
    prior_attempts: list[dict],
) -> dict:
    """Fetch *url* via Bright Data REST and parse with dynamic parser."""
    from app import brightdata
    from app.parsers.dynamic import parse_dynamic

    attempt_record: dict = {"method": "brightdata:unlocker"}

    try:
        result = await brightdata.unlock_url(url)
        html = result.get("body", "")
        attempt_record["status_code"] = result.get("status_code", 0)
        attempt_record["html_size"] = len(html)
    except Exception as exc:
        attempt_record["error"] = str(exc)
        log.warning("Bright Data unlock failed for '%s': %s [%s]", url, exc, request_id)
        return {
            "jobs": [],
            "company_name": company_name or "",
            "url": url,
            "method": f"brightdata:unlocker:{adapter.manifest.family}",
            "adapter_family": adapter.manifest.family,
            "adapter_variant": adapter.manifest.variant,
            "jobs_count": 0,
            "error": str(exc),
            "error_code": EC_NETWORK_ERROR,
            "extraction_attempts": prior_attempts + [attempt_record],
        }

    # Try adapter parser first on unlocked HTML
    jobs = adapter.parse_jobs(html, url, company_name, match_confidence=adapter.match_confidence(url, html=html))
    parse_method = f"brightdata:unlocker:{adapter.manifest.family}"
    dynamic_attempt: dict = {"method": f"adapter:{adapter.manifest.family}", "jobs": len(jobs)}

    if not jobs:
        # Fall through to dynamic parser
        jobs = parse_dynamic(html, url, company_name)
        parse_method = "brightdata:unlocker:dynamic"
        dynamic_attempt = {"method": "dynamic", "jobs": len(jobs)}

    log.info("Bright Data fallback: %d jobs from '%s' [%s]", len(jobs), url, request_id)

    return {
        "jobs": jobs,
        "company_name": jobs[0].get("company_name", company_name or "") if jobs else (company_name or ""),
        "url": url,
        "method": parse_method,
        "adapter_family": "dynamic" if "dynamic" in parse_method else adapter.manifest.family,
        "adapter_variant": "brightdata_unlocker",
        "jobs_count": len(jobs),
        "error": None if jobs else "No jobs found after Bright Data unlock",
        "error_code": None if jobs else EC_PARSE_FAILURE,
        "extraction_attempts": prior_attempts + [attempt_record, dynamic_attempt],
    }


def _should_try_brightdata(adapter, result_or_error_code: str | None) -> bool:
    """Return True if Bright Data fallback is warranted."""
    from app import brightdata as bd
    if not bd.is_configured():
        return False
    if result_or_error_code in _BRIGHTDATA_TRIGGER_CODES:
        return True
    # Always try for generic adapter with zero jobs
    if adapter.manifest.family == "generic" and result_or_error_code == EC_PARSE_FAILURE:
        return True
    return False


# ── API-first path ────────────────────────────────────────────────────────────

async def _api_first_attempt(
    url: str,
    company_name: str | None,
    adapter,
    request_id: str,
) -> dict | None:
    """Try fetch_api_jobs(); return a result dict or None to fall through."""
    # SiteAdapter defines fetch_api_jobs() returning None by default (opt-in).
    # getattr guard protects against legacy or third-party adapters that predate
    # the API-first pipeline and omit the method entirely.
    fetcher = getattr(adapter, "fetch_api_jobs", None)
    if not callable(fetcher):
        return None
    jobs = await fetcher(url, company_name, request_id)
    if jobs is None:
        return None

    log.info("API-first: %d jobs from '%s' [%s]", len(jobs), url, request_id)
    return {
        "jobs": jobs,
        "company_name": jobs[0].get("company_name", company_name or "") if jobs else (company_name or ""),
        "url": url,
        "method": f"api:{adapter.manifest.family}",
        "adapter_family": adapter.manifest.family,
        "adapter_variant": "api",
        "jobs_count": len(jobs),
        # API returning [] is a trusted "no openings" signal — not a parse
        # failure. Auth/network errors are raised before reaching here.
        "error": None,
        "error_code": None,
        "extraction_attempts": [
            {"method": f"api:{adapter.manifest.family}", "jobs": len(jobs)},
        ],
    }


# ── Scrape quality scoring ────────────────────────────────────────────────────

_ERROR_PENALTIES: dict[str, float] = {
    EC_URL_NOT_FOUND:  0.70,
    EC_IP_BLOCKED:     0.50,
    EC_CAPTCHA:        0.40,
    EC_TIMEOUT:        0.30,
    EC_NETWORK_ERROR:  0.30,
    EC_PARSE_FAILURE:  0.25,
}

_FALLBACK_PENALTIES = {0: 0.0, 1: 0.0, 2: 0.05, 3: 0.10}


def _compute_scrape_quality(result: dict, adapter) -> dict:
    """Return a normalized quality dict for a scrape result.

    Score is 0–1; grade is 'high' (≥0.75), 'medium' (≥0.45), or 'low'.
    Lets consumers distinguish '0 jobs = no openings' (high score, no error)
    from '0 jobs = parse failed' (lower score, error_code set).

    Base score blends adapter_confidence with 0.5 so that generic/unknown
    adapters (confidence ~0.01) land at 'medium' on success rather than 'low'.
    """
    jobs = result.get("jobs") or []
    jobs_count = result.get("jobs_count", len(jobs))
    method = result.get("method", "")
    error_code = result.get("error_code")
    attempts = result.get("extraction_attempts") or []
    listing_url = result.get("url", "")

    # Adapter confidence — URL-only proxy (HTML was consumed during parse)
    adapter_confidence = round(adapter.match_confidence(listing_url), 3)

    # Fallback depth — check method_prefix first, then scan attempts list.
    # Botasaurus and brightdata checked before playwright-retry to avoid ties.
    method_prefix = method.split(":")[0] if method else ""
    attempt_methods = [a.get("method") or "" for a in attempts]
    if method_prefix in ("api", "jsonld"):
        fallback_depth = 0
    elif any("botasaurus" in m for m in attempt_methods):
        fallback_depth = 3
    elif any("brightdata" in m for m in attempt_methods):
        fallback_depth = 2
    elif sum(1 for m in attempt_methods if "playwright" in m) > 1:
        fallback_depth = 2
    else:
        fallback_depth = 1

    used_fallback = fallback_depth >= 2

    # Coverage ratios — use len(jobs) not jobs_count; jobs may be [] if stripped
    n = len(jobs)
    if n > 0:
        desc_coverage = round(
            sum(1 for j in jobs if j.get("description") or j.get("snippet")) / n, 3
        )
        url_coverage = round(
            sum(1 for j in jobs if j.get("url") and j.get("url") != listing_url) / n, 3
        )
    else:
        desc_coverage = 0.0
        url_coverage = 0.0

    # Blend confidence with 0.5 neutral so unknown adapters score 'medium' on
    # success rather than 'low' (generic adapter confidence is ~0.01).
    score = 0.5 + 0.5 * adapter_confidence
    score -= _ERROR_PENALTIES.get(error_code, 0.0)
    score -= _FALLBACK_PENALTIES.get(fallback_depth, 0.10)
    score = round(max(0.0, min(1.0, score)), 3)

    grade = "high" if score >= 0.75 else ("medium" if score >= 0.45 else "low")

    return {
        "score": score,
        "grade": grade,
        "signals": {
            "jobs_found": jobs_count,
            "adapter_confidence": adapter_confidence,
            "used_fallback": used_fallback,
            "fallback_depth": fallback_depth,
            "error_code": error_code,
            "parse_method": method,
            "description_coverage": desc_coverage,
            "url_coverage": url_coverage,
        },
    }


# ── Main entry point ──────────────────────────────────────────────────────────


async def scrape_url(
    url: str,
    company_name: str | None = None,
    timeout: int = 30_000,
    *,
    debug: bool = False,
    deep: bool = False,
    request_id: str = "",
    ignored_title_patterns: list[dict] | None = None,
) -> dict:
    """Scrape *url* and return parsed job listings.

    Strategy order:
      1. API-first adapter (if available)
      2. Playwright with retries
      3. Bright Data REST fallback (if configured and warranted)
      4. Botasaurus fallback (for non-API-capture adapters)
    """
    adapter = get_adapter(url)
    result = await _scrape_url(
        url, company_name, timeout,
        adapter=adapter, debug=debug, deep=deep,
        request_id=request_id, ignored_title_patterns=ignored_title_patterns,
    )
    quality = _compute_scrape_quality(result, adapter)
    result["scrape_quality"] = quality
    result.setdefault("artifact_refs", {})["scrape_quality"] = quality
    return result


async def _scrape_url(
    url: str,
    company_name: str | None = None,
    timeout: int = 30_000,
    *,
    adapter,
    debug: bool = False,
    deep: bool = False,
    request_id: str = "",
    ignored_title_patterns: list[dict] | None = None,
) -> dict:
    """Internal scrape implementation — called by scrape_url() which attaches quality."""

    blocked, cb_ec = _cb_check(url)
    if blocked:
        log.warning("Circuit breaker open for '%s' (%s) — skipping scrape [%s]", url, cb_ec, request_id)
        return {
            "jobs": [],
            "company_name": company_name or "",
            "url": url,
            "method": f"playwright:{adapter.manifest.family}",
            "adapter_family": adapter.manifest.family,
            "adapter_variant": adapter.manifest.variant,
            "jobs_count": 0,
            "error": f"Domain temporarily blocked ({cb_ec}). Skipping — will retry after cooldown.",
            "error_code": cb_ec,
            "extraction_attempts": [{"method": "circuit_breaker", "error_code": cb_ec}],
        }

    # ── Step 0: Single job detail page — JSON-LD fast path ───────────────────
    if is_detail_page(url):
        log.info("Detail page detected for '%s' [%s]", url, request_id)
        detail_attempt = await _scrape_attempt(
            url=url,
            company_name=company_name,
            timeout=timeout,
            debug=True,
            deep=False,
            ignored_title_patterns=[],
            adapter=adapter,
            parser_name=adapter.manifest.family,
            user_agent=random.choice(_USER_AGENTS),
            request_id=request_id,
        )
        job = extract_job_from_detail_page(
            detail_attempt.get("html_sample", "") or "",
            url,
            company_name,
        )
        if job:
            log.info("JSON-LD detail extraction: '%s' [%s]", job["title"], request_id)
            return {
                "jobs": [job],
                "jobs_count": 1,
                "company_name": job["company_name"],
                "url": url,
                "method": "jsonld:detail_page",
                "adapter_family": "jsonld",
                "adapter_variant": "detail_page",
                "error": None,
                "error_code": None,
                "extraction_attempts": [{"method": "jsonld:detail_page", "jobs": 1}],
            }
        log.info("No JSON-LD on detail page '%s', falling through [%s]", url, request_id)


    # ── Step 1: API-first ─────────────────────────────────────────────────────
    api_result = await _api_first_attempt(url, company_name, adapter, request_id)
    if api_result is not None:
        return api_result

    # ── Step 1b: BrightData API proxy (when direct API was blocked) ───────────
    bd_api_result = await _brightdata_api_fallback(url, company_name, adapter, request_id)
    if bd_api_result is not None:
        return bd_api_result

    # ── Step 2: Playwright with retries ───────────────────────────────────────
    parser_name = adapter.manifest.family
    last_error: str | None = None
    last_exc: BaseException | None = None
    playwright_attempts: list[dict] = []

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            result = await _scrape_attempt(
                url=url,
                company_name=company_name,
                timeout=timeout,
                debug=debug,
                deep=deep,
                ignored_title_patterns=ignored_title_patterns or [],
                adapter=adapter,
                parser_name=parser_name,
                user_agent=_USER_AGENTS[(attempt - 1) % len(_USER_AGENTS)],
                request_id=request_id,
            )
            if attempt > 1:
                log.info("'%s' scrape succeeded on attempt %d [%s]", url, attempt, request_id)

            playwright_attempts.append({
                "method": result.get("method", f"playwright:{adapter.manifest.family}"),
                "jobs": result.get("jobs_count", 0),
                "attempt": attempt,
                "error_code": result.get("error_code"),
            })
            result.setdefault("extraction_attempts", [])
            result["extraction_attempts"] = playwright_attempts + result["extraction_attempts"]

            ec = result.get("error_code")
            if ec in _NON_RETRYABLE:
                _cb_trip(url, ec)

            # Bright Data fallback for blocked/unknown with zero jobs
            if not result["jobs"] and _should_try_brightdata(adapter, ec):
                log.info("Zero jobs from Playwright (%s) — trying Bright Data fallback [%s]", ec, request_id)
                return await _brightdata_fallback(url, company_name, adapter, request_id, playwright_attempts)

            return result

        except Exception as exc:
            last_error = str(exc)
            last_exc = exc
            ec = _classify_error(exc)
            playwright_attempts.append({
                "method": f"playwright:{adapter.manifest.family}",
                "attempt": attempt,
                "error_code": ec,
                "error": last_error[:200],
            })
            error_type = "timeout" if isinstance(exc, PlaywrightTimeout) else "error"
            log.warning(
                "Scrape attempt %d/%d %s for '%s': %s [%s]",
                attempt, _MAX_RETRIES, error_type, url, last_error, request_id,
            )
            if ec in _NON_RETRYABLE:
                log.info("Non-retryable error '%s' on attempt %d for '%s' — stopping [%s]", ec, attempt, url, request_id)
                _cb_trip(url, ec)
                break
            if attempt < _MAX_RETRIES:
                delay = min(_RETRY_BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 0.5), _RETRY_MAX_DELAY)
                log.debug("Retrying in %.1fs [%s]", delay, request_id)
                await asyncio.sleep(delay)

    final_ec = _classify_error(last_exc)
    log.error("All %d Playwright attempts failed for '%s': %s [%s]", _MAX_RETRIES, url, last_error, request_id)

    # ── Step 3: Bright Data fallback ──────────────────────────────────────────
    if _should_try_brightdata(adapter, final_ec):
        log.info("Playwright failed (%s) — trying Bright Data fallback [%s]", final_ec, request_id)
        return await _brightdata_fallback(url, company_name, adapter, request_id, playwright_attempts)

    # ── Step 4: Botasaurus fallback ───────────────────────────────────────────
    if not getattr(adapter.manifest, "api_capture_support", False):
        try:
            async with _BROWSER_SEM:
                bota_result = await botasaurus_scrape(url, adapter, company_name, request_id, timeout=timeout / 1000)
            bota_result.setdefault("extraction_attempts", [])
            bota_result["extraction_attempts"] = playwright_attempts + bota_result["extraction_attempts"]
            return bota_result
        except Exception as bota_exc:
            log.error("Botasaurus fallback also failed for '%s': %s [%s]", url, bota_exc, request_id)
            last_error = str(bota_exc)
            final_ec = _classify_error(bota_exc)
    else:
        log.info("Skipping botasaurus for API-capture adapter '%s' [%s]", adapter.manifest.family, request_id)

    return {
        "jobs": [],
        "company_name": company_name or "",
        "url": url,
        "method": f"botasaurus:{adapter.manifest.family}",
        "adapter_family": adapter.manifest.family,
        "adapter_variant": adapter.manifest.variant,
        "jobs_count": 0,
        "error": last_error,
        "error_code": final_ec,
        "extraction_attempts": playwright_attempts,
    }


async def _scrape_attempt(
    *,
    url: str,
    company_name: str | None,
    timeout: int,
    debug: bool,
    deep: bool,
    ignored_title_patterns: list[dict],
    adapter,
    parser_name: str,
    user_agent: str,
    request_id: str,
) -> dict:
    """Single attempt to scrape *url*.  Raises on any failure so the caller
    can retry."""
    selectors = list(adapter.manifest.wait_selectors)

    use_remote_browser = adapter.manifest.needs_residential_proxy and bool(_brightdata_browser_ws())

    async with _BROWSER_SEM:
        async with async_playwright() as p:
            if use_remote_browser:
                ws_url = _brightdata_browser_ws()
                log.debug("Using BrightData Browser API for %s [%s]", adapter.manifest.family, request_id)
                browser = await p.chromium.connect_over_cdp(ws_url)
            else:
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

            # Navigate — remote browsers skip networkidle (BrightData handles JS rendering)
            if use_remote_browser:
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                except Exception as exc:
                    if "ERR_HTTP_RESPONSE_CODE_FAILURE" in str(exc):
                        log.debug("Non-2xx HTTP status from remote browser (proceeding): %s [%s]", exc, request_id)
                    else:
                        raise
                # If the page uses Alpine.js, wait for it to initialise before
                # reading the DOM. Uses a short timeout so non-Alpine pages
                # continue without penalty.
                try:
                    await page.wait_for_selector("[x-data]", state="attached", timeout=3_000)
                    await page.wait_for_timeout(400)
                except PlaywrightTimeout:
                    pass  # Not an Alpine page — proceed with what we have
            else:
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

            await page.wait_for_timeout(5_000 if use_remote_browser else 2_000)
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

            # ── Filter ignored titles before detail fetches ─────────────────
            ignored_count = 0
            effective_ignored = _BASELINE_IGNORED_TITLES + (ignored_title_patterns or [])
            if effective_ignored and jobs:
                filtered = []
                for _job in jobs:
                    if _is_ignored_title(_job.get("title", ""), effective_ignored):
                        ignored_count += 1
                    else:
                        filtered.append(_job)
                if ignored_count:
                    log.info("Ignored %d jobs by title pattern [%s]", ignored_count, request_id)
                jobs = filtered

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

    ignored_count = locals().get("ignored_count", 0)  # set inside browser context above

    # Classify soft failures (0 jobs) from the rendered HTML
    soft_error_code: str | None = None
    if not jobs:
        soft_error_code = _classify_error(None, final_html)
        if soft_error_code != EC_PARSE_FAILURE:
            log.warning("Soft block detected for '%s': %s [%s]", url, soft_error_code, request_id)

    result: dict = {
        "jobs": jobs,
        "company_name": jobs[0]["company_name"] if jobs and jobs[0].get("company_name") else (company_name or ""),
        "url": url,
        "method": f"playwright:{parser_name}",
        "adapter_family": adapter.manifest.family,
        "adapter_variant": adapter.manifest.variant,
        "jobs_count": len(jobs),
        "ignored_count": ignored_count,
        "error": None,
        "error_code": soft_error_code,
        "extraction_attempts": [],
    }
    if debug:
        result["html_sample"] = final_html[:60_000]
        result["html_size"] = len(final_html)
        if page_context.get("captured_response_urls"):
            result["captured_response_urls"] = page_context["captured_response_urls"]
            result["captured_response_count"] = len(page_context.get("captured_response_urls", []))
    return result
