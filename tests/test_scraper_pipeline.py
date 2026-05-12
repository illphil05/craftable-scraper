"""Tests for the layered extraction pipeline in scraper.py.

These tests monkeypatch playwright so they can run without a browser installed.
playwright is imported lazily via the monkeypatch to avoid import-time failures.
"""
from __future__ import annotations

import pytest
import sys
import types
from unittest.mock import AsyncMock, MagicMock


# ── Playwright stub (import-time shim so scraper.py can import) ───────────────

def _install_playwright_stub():
    """Install a minimal playwright stub so scraper.py can be imported."""
    if "playwright" in sys.modules:
        return
    pw_mod = types.ModuleType("playwright")
    pw_async = types.ModuleType("playwright.async_api")

    class _FakeTimeoutError(Exception):
        pass

    pw_async.TimeoutError = _FakeTimeoutError
    pw_async.async_playwright = None  # will be patched per-test

    sys.modules["playwright"] = pw_mod
    sys.modules["playwright.async_api"] = pw_async


_install_playwright_stub()


# ── Import scraper after stub is in place ─────────────────────────────────────

import importlib
import app.scraper as scraper_module

# Make sure PlaywrightTimeout resolves from the stub
from playwright.async_api import TimeoutError as _StubbedTimeout
scraper_module.PlaywrightTimeout = _StubbedTimeout


# ── Fake adapter helper ───────────────────────────────────────────────────────

from app.site_adapters.base import SiteAdapter, SiteManifest
from app.parsers.generic import parse as generic_parse


class _FakeAdapter(SiteAdapter):
    def __init__(self, family: str = "generic", *, api_jobs=None, api_capture_support=False):
        self.manifest = SiteManifest(
            family=family,
            variant="base",
            wait_selectors=(),
            api_capture_support=api_capture_support,
            needs_residential_proxy=False,
        )
        self._api_jobs = api_jobs
        self.parser_version = "1.0"
        self.adapter_version = "1.0"
        self.detail_limit = 50
        self.detail_timeout_ms = 15_000

    async def fetch_api_jobs(self, url, company_name, request_id):
        return self._api_jobs

    async def prepare_page(self, page, request_id):
        return {"captured_response_urls": []}

    async def finalize_html(self, page, html, page_context, request_id):
        return html

    def match_confidence(self, url, html=None, response_urls=None):
        return 0.9

    def parse_jobs(self, html, url, company_name=None, *, match_confidence=1.0):
        return []


# ── API-first path ────────────────────────────────────────────────────────────

async def test_api_first_returns_jobs_without_playwright(monkeypatch):
    """When fetch_api_jobs() returns jobs, Playwright must not be launched."""
    api_jobs = [{"title": "Chef", "company_name": "Acme", "url": "https://example.com/jobs/1"}]
    adapter = _FakeAdapter("greenhouse", api_jobs=api_jobs, api_capture_support=True)

    playwright_launched = []

    def fake_get_adapter(url, html=None, response_urls=None):
        return adapter

    monkeypatch.setattr(scraper_module, "get_adapter", fake_get_adapter)
    # async_playwright should NOT be called
    monkeypatch.setattr(scraper_module, "async_playwright", lambda: (_ for _ in ()).throw(AssertionError("playwright must not launch")))

    result = await scraper_module.scrape_url(
        "https://boards.greenhouse.io/acme",
        "Acme",
        request_id="req-api-1",
    )

    assert result["jobs_count"] == 1
    assert result["jobs"][0]["title"] == "Chef"
    assert result["method"] == "api:greenhouse"
    assert result["extraction_attempts"][0]["method"] == "api:greenhouse"


async def test_api_first_none_falls_through(monkeypatch):
    """When fetch_api_jobs() returns None, we proceed to Playwright (then fail gracefully)."""
    adapter = _FakeAdapter("greenhouse", api_jobs=None, api_capture_support=True)

    class _BrokenPW:
        async def __aenter__(self):
            raise RuntimeError("simulated playwright failure")
        async def __aexit__(self, *a):
            pass

    monkeypatch.setattr(scraper_module, "get_adapter", lambda *a, **kw: adapter)
    monkeypatch.setattr(scraper_module, "async_playwright", lambda: _BrokenPW())
    # Disable botasaurus (api_capture_support=True skips it already)

    import app.brightdata as bd_mod
    monkeypatch.setattr(bd_mod, "is_configured", lambda: False)

    result = await scraper_module.scrape_url(
        "https://boards.greenhouse.io/acme",
        "Acme",
        request_id="req-api-2",
    )
    # Playwright was attempted and failed; no jobs
    assert result["jobs_count"] == 0
    assert any("playwright" in str(a.get("method", "")) for a in result.get("extraction_attempts", []))


# ── Bright Data fallback ──────────────────────────────────────────────────────

async def test_brightdata_fallback_triggered_on_zero_jobs_generic(monkeypatch):
    """Generic adapter with zero jobs triggers Bright Data fallback."""
    adapter = _FakeAdapter("generic")

    class _FakePW:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        @property
        def chromium(self): return self
        async def launch(self, **kwargs): return _FakeBrowser()
        async def connect_over_cdp(self, ws): return _FakeBrowser()

    class _FakeBrowser:
        async def new_context(self, **kwargs): return _FakeContext()
        async def close(self): pass

    class _FakeContext:
        async def new_page(self): return _FakePage()

    class _FakePage:
        async def add_init_script(self, s): pass
        async def goto(self, url, wait_until, timeout): pass
        async def wait_for_selector(self, sel, timeout, state): raise RuntimeError("not found")
        async def evaluate(self, expr): pass
        async def wait_for_timeout(self, ms): pass
        async def content(self): return "<html><body></body></html>"

    monkeypatch.setattr(scraper_module, "get_adapter", lambda *a, **kw: adapter)
    monkeypatch.setattr(scraper_module, "async_playwright", lambda: _FakePW())

    bd_called = []

    async def fake_bd_fallback(url, company_name, adapter, request_id, prior_attempts):
        bd_called.append(url)
        return {
            "jobs": [{"title": "BD Job", "company_name": "X"}],
            "company_name": "X",
            "url": url,
            "method": "brightdata:unlocker:dynamic",
            "adapter_family": "dynamic",
            "adapter_variant": "brightdata_unlocker",
            "jobs_count": 1,
            "error": None,
            "error_code": None,
            "extraction_attempts": prior_attempts + [{"method": "brightdata:unlocker"}],
        }

    monkeypatch.setattr(scraper_module, "_brightdata_fallback", fake_bd_fallback)

    import app.brightdata as bd_mod
    monkeypatch.setattr(bd_mod, "is_configured", lambda: True)

    result = await scraper_module.scrape_url("https://example.com/careers", request_id="req-bd-1")

    assert bd_called
    assert result["jobs_count"] == 1
    assert result["method"] == "brightdata:unlocker:dynamic"


async def test_brightdata_not_triggered_when_not_configured(monkeypatch):
    """When BRIGHTDATA_API_KEY is absent, Bright Data fallback must not run."""
    adapter = _FakeAdapter("generic")

    class _FakePW:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        @property
        def chromium(self): return self
        async def launch(self, **kwargs): return _FakeBrowser()

    class _FakeBrowser:
        async def new_context(self, **kwargs): return _FakeContext()
        async def close(self): pass

    class _FakeContext:
        async def new_page(self): return _FakePage()

    class _FakePage:
        async def add_init_script(self, s): pass
        async def goto(self, url, wait_until, timeout): pass
        async def wait_for_selector(self, sel, timeout, state): raise RuntimeError("nf")
        async def evaluate(self, expr): pass
        async def wait_for_timeout(self, ms): pass
        async def content(self): return "<html><body></body></html>"

    monkeypatch.setattr(scraper_module, "get_adapter", lambda *a, **kw: adapter)
    monkeypatch.setattr(scraper_module, "async_playwright", lambda: _FakePW())
    monkeypatch.setattr(
        scraper_module, "botasaurus_scrape",
        AsyncMock(return_value={
            "jobs": [], "jobs_count": 0, "method": "botasaurus:generic",
            "adapter_family": "generic", "adapter_variant": "base",
            "company_name": "", "url": "x", "error": None, "error_code": None,
        }),
    )

    import app.brightdata as bd_mod
    monkeypatch.setattr(bd_mod, "is_configured", lambda: False)

    bd_called = []
    original_fallback = scraper_module._brightdata_fallback

    async def tracking_fallback(*a, **kw):
        bd_called.append(True)
        return await original_fallback(*a, **kw)

    monkeypatch.setattr(scraper_module, "_brightdata_fallback", tracking_fallback)

    await scraper_module.scrape_url("https://example.com/careers", request_id="req-bd-2")
    assert bd_called == []


async def test_generic_playwright_zero_jobs_uses_dynamic_fallback(monkeypatch):
    """Unknown domains should run the dynamic parser over rendered Playwright HTML."""
    adapter = _FakeAdapter("generic")
    html = """
    <html><body>
      <article class="opening-card">
        <h2 class="position-title">Rooms Controller</h2>
        <a href="/careers/rooms-controller">Apply</a>
        <div class="job-location">Nashville, TN</div>
      </article>
      <article class="opening-card">
        <h2 class="position-title">Executive Steward</h2>
        <a href="/careers/executive-steward">Apply</a>
        <div class="job-location">Nashville, TN</div>
      </article>
    </body></html>
    """

    class _FakePW:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        @property
        def chromium(self): return self
        async def launch(self, **kwargs): return _FakeBrowser()

    class _FakeBrowser:
        async def new_context(self, **kwargs): return _FakeContext()
        async def close(self): pass

    class _FakeContext:
        async def new_page(self): return _FakePage()

    class _FakePage:
        async def add_init_script(self, s): pass
        async def goto(self, url, wait_until, timeout): pass
        async def wait_for_selector(self, sel, timeout, state): raise RuntimeError("not found")
        async def evaluate(self, expr): pass
        async def wait_for_timeout(self, ms): pass
        async def content(self): return html

    monkeypatch.setattr(scraper_module, "get_adapter", lambda *a, **kw: adapter)
    monkeypatch.setattr(scraper_module, "async_playwright", lambda: _FakePW())

    import app.brightdata as bd_mod
    monkeypatch.setattr(bd_mod, "is_configured", lambda: False)
    monkeypatch.setattr(
        scraper_module,
        "botasaurus_scrape",
        AsyncMock(side_effect=AssertionError("dynamic fallback should prevent botasaurus")),
    )

    result = await scraper_module.scrape_url(
        "https://unknown.example/careers",
        company_name="Unknown Hotel",
        request_id="req-dyn-1",
    )

    assert result["jobs_count"] == 2
    assert result["method"] == "playwright:generic:dynamic"
    assert result["adapter_family"] == "dynamic"
    assert result["adapter_variant"] == "fallback_parser"
    assert {j["title"] for j in result["jobs"]} == {"Rooms Controller", "Executive Steward"}
    assert result["jobs"][0]["source_site_family"] == "dynamic"
    assert any(a["method"] == "dynamic:fallback_parser" for a in result["extraction_attempts"])
    assert result["scrape_quality"]["signals"]["used_fallback"] is True
    assert result["scrape_quality"]["signals"]["fallback_depth"] == 2


# ── extraction_attempts ───────────────────────────────────────────────────────

async def test_extraction_attempts_in_api_first_result(monkeypatch):
    api_jobs = [{"title": "GM", "company_name": "Hotel"}]
    adapter = _FakeAdapter("greenhouse", api_jobs=api_jobs)
    monkeypatch.setattr(scraper_module, "get_adapter", lambda *a, **kw: adapter)

    result = await scraper_module.scrape_url(
        "https://boards.greenhouse.io/hotel", request_id="req-ea-1"
    )
    assert "extraction_attempts" in result
    assert result["extraction_attempts"][0]["method"] == "api:greenhouse"


async def test_circuit_breaker_includes_extraction_attempts(monkeypatch):
    import time
    adapter = _FakeAdapter("generic")
    monkeypatch.setattr(scraper_module, "get_adapter", lambda *a, **kw: adapter)

    scraper_module._circuit_breaker["example.com"] = (scraper_module.EC_IP_BLOCKED, time.monotonic())

    try:
        result = await scraper_module.scrape_url("https://example.com/careers", request_id="req-cb-1")
        assert result["error_code"] == scraper_module.EC_IP_BLOCKED
        assert "extraction_attempts" in result
        assert result["extraction_attempts"][0]["method"] == "circuit_breaker"
    finally:
        scraper_module._circuit_breaker.pop("example.com", None)
