from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.routes import SaveScrapeRequest, _company_website_from_careers_url
from app.url_classifier import derive_careers_root_url


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


# ── _company_website_from_careers_url ─────────────────────────────────────────

def test_derives_origin_from_company_owned_careers_subdomain():
    assert _company_website_from_careers_url("https://careers.acmehotel.com/jobs/123") \
        == "https://careers.acmehotel.com"

def test_strips_path_and_query():
    assert _company_website_from_careers_url("https://www.hilton.com/en/careers?region=us") \
        == "https://www.hilton.com"

def test_returns_none_for_greenhouse():
    assert _company_website_from_careers_url("https://boards.greenhouse.io/acme/jobs/123") is None

def test_returns_none_for_lever():
    assert _company_website_from_careers_url("https://jobs.lever.co/marriott/abc-uuid") is None

def test_returns_none_for_workday():
    assert _company_website_from_careers_url("https://hilton.wd1.myworkdayjobs.com/en-US/HiltonHotels") is None

def test_returns_none_for_ashby():
    assert _company_website_from_careers_url("https://jobs.ashbyhq.com/acme/abc-uuid") is None

def test_returns_none_when_careers_url_is_none():
    assert _company_website_from_careers_url(None) is None

def test_returns_none_for_invalid_url():
    assert _company_website_from_careers_url("not-a-url") is None

def test_does_not_match_ats_name_as_substring_of_company_domain():
    # "taleo.net" must not match "notataleo.net" — suffix check, not substring
    assert _company_website_from_careers_url("https://notataleo.net/careers") \
        == "https://notataleo.net"

def test_prefers_explicit_website_url_via_caller():
    # The helper only derives — callers pass explicit website_url when available.
    # Verify that a known-good URL passes through as-is.
    result = _company_website_from_careers_url("https://careers.marriott.com/jobs/1234")
    assert result == "https://careers.marriott.com"


# ── derive_careers_root_url ───────────────────────────────────────────────────

def test_strips_hcareers_detail_to_listing_root():
    url = "https://www.hcareers.com/jobs/4336093-finance-specialist-grand-casino-onamia-mn"
    assert derive_careers_root_url(url) == "https://www.hcareers.com/jobs"

def test_strips_hospitalityjobs_detail_to_listing_root():
    url = "https://www.hospitalityjobs.com/jobs/9876543-bartender-new-york-ny"
    assert derive_careers_root_url(url) == "https://www.hospitalityjobs.com/jobs"

def test_listing_root_passes_through_unchanged():
    assert derive_careers_root_url("https://www.hcareers.com/jobs") == "https://www.hcareers.com/jobs"

def test_non_job_board_url_passes_through_unchanged():
    assert derive_careers_root_url("https://boards.greenhouse.io/acme/jobs/123") \
        == "https://boards.greenhouse.io/acme/jobs/123"

def test_company_careers_page_passes_through_unchanged():
    assert derive_careers_root_url("https://careers.marriott.com/jobs/1234") \
        == "https://careers.marriott.com/jobs/1234"

def test_empty_string_passes_through():
    assert derive_careers_root_url("") == ""

def test_none_equivalent_passes_through():
    assert derive_careers_root_url("https://example.com") == "https://example.com"


# ── save_scrape website_url derivation ───────────────────────────────────────

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
