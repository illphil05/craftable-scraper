from __future__ import annotations

import pytest

from app import scraper


class _FakeAdapter:
    def __init__(
        self,
        family: str,
        wait_selectors: list[str],
        jobs: list[dict] | None = None,
        *,
        detail_page_support: bool = False,
    ):
        self.manifest = type(
            "Manifest",
            (),
            {
                "family": family,
                "variant": "base",
                "wait_selectors": tuple(wait_selectors),
                "detail_page_support": detail_page_support,
            },
        )()
        self._jobs = jobs or [{"title": f"{family.title()} Job", "company_name": "Example"}]
        self.detail_limit = 99
        self.detail_timeout_ms = 98_000
        self.enrich_calls: list[dict] = []

    async def prepare_page(self, page, request_id: str) -> dict:
        return {"captured_response_urls": []}

    async def finalize_html(self, page, html: str, page_context: dict, request_id: str) -> str:
        return html

    def match_confidence(self, url: str, html: str | None = None, response_urls: list[str] | None = None) -> float:
        return 1.0

    def parse_jobs(self, html: str, url: str, company_name: str | None = None, *, match_confidence: float = 1.0) -> list[dict]:
        return list(self._jobs)

    async def enrich_jobs(
        self,
        page,
        jobs: list[dict],
        request_id: str,
        *,
        detail_limit: int | None = None,
        detail_timeout_ms: int | None = None,
    ) -> list[dict]:
        self.enrich_calls.append(
            {
                "page": page,
                "jobs": list(jobs),
                "request_id": request_id,
                "detail_limit": detail_limit,
                "detail_timeout_ms": detail_timeout_ms,
            }
        )
        return jobs


class _FakePage:
    def __init__(self):
        self.waited_selectors: list[str] = []

    async def add_init_script(self, script: str) -> None:
        return None

    async def goto(self, url: str, wait_until: str, timeout: int) -> None:
        return None

    async def wait_for_selector(self, selector: str, timeout: int, state: str) -> None:
        self.waited_selectors.append(selector)
        if selector == ".resolved-selector":
            return
        raise RuntimeError("selector not found")

    async def evaluate(self, expression: str) -> None:
        return None

    async def wait_for_timeout(self, timeout_ms: int) -> None:
        return None

    async def content(self) -> str:
        return "<html><body><div class='resolved-selector'>job</div></body></html>"


class _FakeContext:
    def __init__(self, page: _FakePage):
        self._page = page

    async def new_page(self) -> _FakePage:
        return self._page


class _FakeBrowser:
    def __init__(self, page: _FakePage):
        self._page = page

    async def new_context(self, user_agent: str, viewport: dict) -> _FakeContext:
        return _FakeContext(self._page)

    async def close(self) -> None:
        return None


class _FakePlaywright:
    def __init__(self, page: _FakePage):
        self.chromium = self
        self._page = page

    async def launch(self, headless: bool, args: list[str]) -> _FakeBrowser:
        return _FakeBrowser(self._page)


class _FakePlaywrightManager:
    def __init__(self, page: _FakePage):
        self._playwright = _FakePlaywright(page)

    async def __aenter__(self) -> _FakePlaywright:
        return self._playwright

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.mark.asyncio
async def test_scrape_attempt_waits_for_resolved_adapter_selectors(monkeypatch):
    page = _FakePage()
    initial_adapter = _FakeAdapter("initial", [".initial-selector"])
    resolved_adapter = _FakeAdapter("resolved", [".resolved-selector"])

    def fake_get_adapter(url: str, html: str | None = None, response_urls: list[str] | None = None):
        if html is None:
            return initial_adapter
        return resolved_adapter

    monkeypatch.setattr(scraper, "get_adapter", fake_get_adapter)
    monkeypatch.setattr(scraper, "async_playwright", lambda: _FakePlaywrightManager(page))

    result = await scraper._scrape_attempt(
        url="https://example.com/careers",
        company_name="Example",
        timeout=1_000,
        debug=False,
        deep=False,
        adapter=initial_adapter,
        parser_name=initial_adapter.manifest.family,
        user_agent="test-agent",
        request_id="req-1",
    )

    assert ".initial-selector" in page.waited_selectors
    assert ".resolved-selector" in page.waited_selectors
    assert result["method"] == "playwright:resolved"
    assert result["adapter_family"] == "resolved"


@pytest.mark.asyncio
async def test_scrape_attempt_passes_deep_scrape_settings_without_mutating_adapter(monkeypatch):
    page = _FakePage()
    deep_jobs = [{"title": "Resolved Job", "company_name": "Example", "url": "https://example.com/job/1"}]
    initial_adapter = _FakeAdapter("initial", [".initial-selector"])
    resolved_adapter = _FakeAdapter(
        "resolved",
        [".resolved-selector"],
        jobs=deep_jobs,
        detail_page_support=True,
    )

    def fake_get_adapter(url: str, html: str | None = None, response_urls: list[str] | None = None):
        if html is None:
            return initial_adapter
        return resolved_adapter

    monkeypatch.setattr(scraper, "get_adapter", fake_get_adapter)
    monkeypatch.setattr(scraper, "async_playwright", lambda: _FakePlaywrightManager(page))

    original_detail_limit = resolved_adapter.detail_limit
    original_detail_timeout_ms = resolved_adapter.detail_timeout_ms

    await scraper._scrape_attempt(
        url="https://example.com/careers",
        company_name="Example",
        timeout=1_000,
        debug=False,
        deep=True,
        adapter=initial_adapter,
        parser_name=initial_adapter.manifest.family,
        user_agent="test-agent",
        request_id="req-2",
    )

    assert resolved_adapter.enrich_calls == [
        {
            "page": page,
            "jobs": deep_jobs,
            "request_id": "req-2",
            "detail_limit": scraper.DEEP_SCRAPE_LIMIT,
            "detail_timeout_ms": scraper.DEEP_PAGE_TIMEOUT,
        }
    ]
    assert resolved_adapter.detail_limit == original_detail_limit
    assert resolved_adapter.detail_timeout_ms == original_detail_timeout_ms
