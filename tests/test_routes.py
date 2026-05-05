from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.routes import SaveScrapeRequest


def test_save_scrape_request_uses_independent_mutable_defaults():
    first = SaveScrapeRequest(
        careers_url="https://example.com/careers",
        parser_used="playwright:generic",
        jobs_found=0,
        elapsed_ms=1,
    )
    second = SaveScrapeRequest(
        careers_url="https://example.com/careers",
        parser_used="playwright:generic",
        jobs_found=0,
        elapsed_ms=1,
    )

    first.artifact_refs["html_size"] = 100
    first.jobs.append({"title": "Chef"})

    assert second.artifact_refs == {}
    assert second.jobs == []


def _make_test_client():
    from fastapi import FastAPI
    from app.routes import router as api_router
    _app = FastAPI()
    _app.include_router(api_router)
    return TestClient(_app, raise_server_exceptions=True)


def test_save_scrape_derives_safe_website_url_for_malformed_careers_url():
    mock_company = {"id": 42, "name": "Test Co", "careers_url": "relative/path"}
    with (
        patch("app.routes.db.find_company_by_careers_url", new_callable=AsyncMock, return_value=None),
        patch("app.routes.db.create_company", new_callable=AsyncMock, return_value=mock_company) as mock_create,
        patch("app.routes.db.save_scrape", new_callable=AsyncMock, return_value=1),
        patch("app.routes.db.get_company", new_callable=AsyncMock, return_value=mock_company),
    ):
        _make_test_client().post(
            "/api/save-scrape",
            json={
                "company_name": "Test Co",
                "careers_url": "relative/path",
                "parser_used": "playwright:generic",
                "jobs_found": 0,
                "elapsed_ms": 100,
            },
        )

    assert mock_create.called
    website_url = mock_create.call_args.kwargs.get("website_url")
    assert website_url != "://"


def test_save_scrape_derives_domain_as_website_url_for_valid_careers_url():
    mock_company = {"id": 7, "name": "OHMC", "careers_url": "https://jobs.dayforcehcm.com/en-US/ohmc/CANDIDATEPORTAL/jobs"}
    with (
        patch("app.routes.db.find_company_by_careers_url", new_callable=AsyncMock, return_value=None),
        patch("app.routes.db.create_company", new_callable=AsyncMock, return_value=mock_company) as mock_create,
        patch("app.routes.db.save_scrape", new_callable=AsyncMock, return_value=1),
        patch("app.routes.db.get_company", new_callable=AsyncMock, return_value=mock_company),
    ):
        _make_test_client().post(
            "/api/save-scrape",
            json={
                "company_name": "OHMC",
                "careers_url": "https://jobs.dayforcehcm.com/en-US/ohmc/CANDIDATEPORTAL/jobs",
                "parser_used": "playwright:dayforce",
                "jobs_found": 1,
                "elapsed_ms": 800,
            },
        )

    website_url = mock_create.call_args.kwargs.get("website_url")
    assert website_url == "https://jobs.dayforcehcm.com"
