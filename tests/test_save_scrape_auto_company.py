"""Tests for POST /api/save-scrape auto-company creation with website_url.

These tests call the route handler directly (no full ASGI stack needed)
so they work without apscheduler or playwright being installed.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app import db
from app.routes import SaveScrapeRequest, save_scrape as save_scrape_handler


@pytest.fixture(autouse=True)
async def tmp_db(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_file))
    monkeypatch.setattr(db, "_conn", None)
    monkeypatch.setattr(db, "_conn_lock", None)
    await db.init_db()
    yield str(db_file)
    if db._conn is not None:
        await db._conn.close()
        monkeypatch.setattr(db, "_conn", None)


async def _call_save_scrape(**kwargs) -> dict:
    """Helper: build request body and invoke the handler directly."""
    defaults = {
        "careers_url": "https://boards.greenhouse.io/acmecorp",
        "parser_used": "playwright:generic",
        "jobs_found": 0,
        "elapsed_ms": 100,
    }
    defaults.update(kwargs)
    body = SaveScrapeRequest(**defaults)
    # Patch outreach so no network calls are made
    with patch("app.routes.push_to_outreach", new=AsyncMock(return_value=None)):
        return await save_scrape_handler(body)


async def test_save_scrape_auto_creates_company_with_website_url():
    """When company_id is absent, auto-created company gets website_url derived from careers_url."""
    result = await _call_save_scrape(
        careers_url="https://boards.greenhouse.io/acmecorp",
        company_name="Acme Corp",
        parser_used="playwright:greenhouse",
        adapter_family="greenhouse",
        adapter_variant="api",
        jobs_found=2,
        elapsed_ms=500,
        jobs=[
            {"title": "Chef", "company_name": "Acme Corp", "url": "https://boards.greenhouse.io/acmecorp/1"},
            {"title": "Server", "company_name": "Acme Corp", "url": "https://boards.greenhouse.io/acmecorp/2"},
        ],
    )
    assert result["ok"] is True
    company = result["company"]
    assert company["name"] == "Acme Corp"
    assert company["website_url"] == "https://boards.greenhouse.io"
    assert company["site_family"] == "greenhouse"
    assert company["site_variant"] == "api"


async def test_save_scrape_finds_existing_company_by_careers_url():
    """When a company with the same careers_url already exists, it is reused."""
    existing = await db.create_company(
        "Existing Co",
        careers_url="https://jobs.lever.co/existingco",
        website_url="https://www.existingco.com",
    )
    result = await _call_save_scrape(
        careers_url="https://jobs.lever.co/existingco",
        company_id=None,
        company_name=None,
        parser_used="playwright:lever",
        jobs_found=0,
        elapsed_ms=200,
    )
    assert result["company_id"] == existing["id"]


async def test_save_scrape_carries_adapter_metadata():
    """adapter_family and adapter_variant must be saved to scrape_history."""
    result = await _call_save_scrape(
        careers_url="https://jobs.smartrecruiters.com/MetaCo",
        company_name="Meta Co",
        parser_used="api:smartrecruiters",
        adapter_family="smartrecruiters",
        adapter_variant="api",
        jobs_found=5,
        elapsed_ms=300,
    )
    company_id = result["company_id"]
    history = await db.get_scrape_history(company_id)
    assert history[0]["adapter_family"] == "smartrecruiters"
    assert history[0]["adapter_variant"] == "api"


async def test_save_scrape_derives_website_url_from_lever_careers_url():
    """website_url must be derived correctly for Lever-style careers URLs."""
    result = await _call_save_scrape(
        careers_url="https://jobs.lever.co/somecafe",
        company_name="Some Cafe",
        parser_used="api:lever",
        adapter_family="lever",
        adapter_variant="api",
        jobs_found=3,
        elapsed_ms=150,
    )
    company = result["company"]
    assert company["website_url"] == "https://jobs.lever.co"
