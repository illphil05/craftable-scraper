"""Tests for botasaurus fallback scraper."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest


class _FakeAdapter:
    class manifest:
        family = "greenhouse"
        variant = "base"

    @staticmethod
    def parse_jobs(html, url, company_name=None, *, match_confidence=1.0):
        if "<job>" in html:
            return [{"title": "Chef", "company_name": company_name or "Acme"}]
        return []


def _make_fake_driver(html: str):
    driver = MagicMock()
    driver.page_html = html
    return driver


@pytest.mark.asyncio
async def test_botasaurus_scrape_returns_jobs():
    """botasaurus_scrape returns parsed jobs when driver succeeds."""
    fake_html = "<html><job>Chef</job></html>"

    with patch("app.botasaurus_scraper._sync_botasaurus_get", return_value=fake_html):
        from app.botasaurus_scraper import botasaurus_scrape
        result = await botasaurus_scrape(
            url="https://boards.greenhouse.io/acme",
            adapter=_FakeAdapter(),
            company_name="Acme",
            request_id="test-1",
        )

    assert result["jobs_count"] == 1
    assert result["method"] == "botasaurus:greenhouse"
    assert result["error"] is None


@pytest.mark.asyncio
async def test_botasaurus_scrape_empty_html_returns_zero_jobs():
    """botasaurus_scrape with no matching HTML returns empty jobs list, no error."""
    with patch("app.botasaurus_scraper._sync_botasaurus_get", return_value="<html></html>"):
        from app.botasaurus_scraper import botasaurus_scrape
        result = await botasaurus_scrape(
            url="https://boards.greenhouse.io/acme",
            adapter=_FakeAdapter(),
            company_name="Acme",
            request_id="test-2",
        )

    assert result["jobs_count"] == 0
    assert result["error"] is None
    assert result["method"] == "botasaurus:greenhouse"


@pytest.mark.asyncio
async def test_botasaurus_scrape_driver_error_raises():
    """botasaurus_scrape propagates driver exceptions so caller can handle."""
    with patch("app.botasaurus_scraper._sync_botasaurus_get", side_effect=RuntimeError("blocked")):
        from app.botasaurus_scraper import botasaurus_scrape
        with pytest.raises(RuntimeError, match="blocked"):
            await botasaurus_scrape(
                url="https://boards.greenhouse.io/acme",
                adapter=_FakeAdapter(),
                company_name="Acme",
                request_id="test-3",
            )
