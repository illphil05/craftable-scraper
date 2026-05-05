from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.scheduler import _PAGE_SIZE, _run_scheduled_scrape


def _company(i: int, with_url: bool = True) -> dict:
    return {
        "id": f"c{i}",
        "name": f"Company {i}",
        "careers_url": f"https://example.com/{i}/careers" if with_url else None,
        "region": "US",
    }


def _scrape_result(jobs: list[dict] | None = None) -> dict:
    return {
        "method": "playwright:generic",
        "adapter_family": "generic",
        "adapter_variant": "base",
        "jobs_count": len(jobs or []),
        "jobs": jobs or [],
        "elapsed_ms": 100,
        "error": None,
        "error_code": None,
        "html_size": 1000,
    }


@pytest.mark.asyncio
async def test_scheduled_scrape_saves_correctly():
    """db.save_scrape receives adapter_family, adapter_variant, artifact_refs, error_code."""
    company = _company(1)
    jobs = [{"title": "Chef", "url": "https://example.com/job/1"}]
    result = _scrape_result(jobs)

    with (
        patch("app.scheduler.db.list_companies", new_callable=AsyncMock) as mock_list,
        patch("app.scheduler.db.save_scrape", new_callable=AsyncMock, return_value="s1") as mock_save,
        patch("app.scheduler.db.save_jobs", new_callable=AsyncMock),
        patch("app.scheduler.scrape_url", new_callable=AsyncMock, return_value=result),
        patch("app.scheduler.push_to_outreach", new_callable=AsyncMock, return_value={"ok": True, "skipped": False}),
    ):
        mock_list.return_value = {"companies": [company]}
        await _run_scheduled_scrape()

    mock_save.assert_called_once_with(
        company_id="c1",
        url=company["careers_url"],
        parser_used="playwright:generic",
        adapter_family="generic",
        adapter_variant="base",
        jobs_found=1,
        elapsed_ms=100,
        error=None,
        error_code=None,
        html_size=1000,
        artifact_refs={},
        deep=False,
    )


@pytest.mark.asyncio
async def test_scheduled_scrape_pushes_to_outreach():
    """push_to_outreach is called with a correctly formed payload after a successful scrape."""
    company = _company(1)
    jobs = [{"title": "Chef", "url": "https://example.com/job/1"}]
    result = _scrape_result(jobs)

    with (
        patch("app.scheduler.db.list_companies", new_callable=AsyncMock) as mock_list,
        patch("app.scheduler.db.save_scrape", new_callable=AsyncMock, return_value="s1"),
        patch("app.scheduler.db.save_jobs", new_callable=AsyncMock),
        patch("app.scheduler.scrape_url", new_callable=AsyncMock, return_value=result),
        patch("app.scheduler.push_to_outreach", new_callable=AsyncMock, return_value={"ok": True, "skipped": False}) as mock_push,
    ):
        mock_list.return_value = {"companies": [company]}
        await _run_scheduled_scrape()

    mock_push.assert_called_once()
    payload = mock_push.call_args[0][0]
    assert payload["source"] == "craftable_scraper"
    assert payload["careers_url"] == company["careers_url"]
    assert len(payload["jobs"]) == 1
    assert payload["jobs"][0]["company_name"] == "Company 1"


@pytest.mark.asyncio
async def test_scheduled_scrape_paginates():
    """Pagination fetches all pages; full page + partial page = all companies processed."""
    full_page = [_company(i) for i in range(_PAGE_SIZE)]
    partial_page = [_company(i + _PAGE_SIZE) for i in range(3)]

    page_responses = [
        {"companies": full_page},
        {"companies": partial_page},
    ]

    with (
        patch("app.scheduler.db.list_companies", new_callable=AsyncMock, side_effect=page_responses) as mock_list,
        patch("app.scheduler.db.save_scrape", new_callable=AsyncMock, return_value="s1"),
        patch("app.scheduler.db.save_jobs", new_callable=AsyncMock),
        patch("app.scheduler.scrape_url", new_callable=AsyncMock, return_value=_scrape_result()) as mock_scrape,
        patch("app.scheduler.push_to_outreach", new_callable=AsyncMock, return_value={"ok": False, "skipped": True}),
    ):
        await _run_scheduled_scrape()

    assert mock_list.call_count == 2
    assert mock_list.call_args_list[0] == call(page=1, limit=_PAGE_SIZE)
    assert mock_list.call_args_list[1] == call(page=2, limit=_PAGE_SIZE)
    assert mock_scrape.call_count == _PAGE_SIZE + 3


@pytest.mark.asyncio
async def test_scheduled_scrape_skip_no_careers_url():
    """Companies without careers_url are filtered out and never scraped."""
    companies = [_company(1, with_url=False), _company(2, with_url=False)]

    with (
        patch("app.scheduler.db.list_companies", new_callable=AsyncMock) as mock_list,
        patch("app.scheduler.scrape_url", new_callable=AsyncMock) as mock_scrape,
    ):
        mock_list.return_value = {"companies": companies}
        await _run_scheduled_scrape()

    mock_scrape.assert_not_called()
