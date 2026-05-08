"""Tests for API-first adapters (Greenhouse, Lever, SmartRecruiters)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.site_adapters.greenhouse import GreenhouseAdapter, _parse_board_token, _normalize_greenhouse_jobs
from app.site_adapters.lever import LeverAdapter, _parse_company as lever_parse_company, _normalize_lever_jobs
from app.site_adapters.smartrecruiters import SmartRecruitersAdapter, _parse_company as sr_parse_company, _normalize_sr_jobs


# ── Greenhouse ────────────────────────────────────────────────────────────────

def test_greenhouse_board_token_standard():
    assert _parse_board_token("https://boards.greenhouse.io/acmecorp") == "acmecorp"


def test_greenhouse_board_token_embed():
    assert _parse_board_token("https://boards.greenhouse.io/embed/job_board?for=testco") == "testco"


def test_greenhouse_board_token_unrecognized():
    assert _parse_board_token("https://unknown.example.com/careers") is None


def test_normalize_greenhouse_jobs_basic():
    data = {
        "jobs": [
            {
                "title": "Executive Chef",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
                "location": {"name": "New York, NY"},
                "departments": [{"name": "Food & Beverage"}],
                "content": "<p>Full description</p>",
            }
        ]
    }
    jobs = _normalize_greenhouse_jobs(data, "Acme Hotel")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Executive Chef"
    assert jobs[0]["location"] == "New York, NY"
    assert jobs[0]["department"] == "Food & Beverage"
    assert jobs[0]["description"] == "<p>Full description</p>"
    assert jobs[0]["source_confidence"] == 0.98
    assert jobs[0]["extraction_method"] == "api:greenhouse"


def test_normalize_greenhouse_jobs_empty_title_skipped():
    data = {"jobs": [{"title": "", "absolute_url": "https://example.com/jobs/1"}]}
    jobs = _normalize_greenhouse_jobs(data, "Test Co")
    assert jobs == []


@pytest.mark.asyncio
async def test_greenhouse_fetch_api_jobs_success():
    adapter = GreenhouseAdapter()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "jobs": [
            {"title": "Line Cook", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
             "location": {"name": "Chicago"}, "departments": [], "content": None},
        ]
    }

    with patch("httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

        jobs = await adapter.fetch_api_jobs(
            "https://boards.greenhouse.io/acme",
            "Acme",
            "req-1",
        )

    assert jobs is not None
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Line Cook"
    assert jobs[0]["extraction_method"] == "api:greenhouse"


@pytest.mark.asyncio
async def test_greenhouse_fetch_api_jobs_no_token_returns_none():
    adapter = GreenhouseAdapter()
    result = await adapter.fetch_api_jobs("https://example.com/careers", None, "req-1")
    assert result is None


@pytest.mark.asyncio
async def test_greenhouse_fetch_api_jobs_http_error_returns_none():
    adapter = GreenhouseAdapter()
    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch("httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await adapter.fetch_api_jobs("https://boards.greenhouse.io/noexist", None, "req-2")

    assert result is None


# ── Lever ─────────────────────────────────────────────────────────────────────

def test_lever_parse_company_standard():
    assert lever_parse_company("https://jobs.lever.co/acmecorp") == "acmecorp"


def test_lever_parse_company_with_path():
    assert lever_parse_company("https://jobs.lever.co/acmecorp/abc123") == "acmecorp"


def test_lever_parse_company_unrecognized():
    assert lever_parse_company("https://example.com/careers") is None


def test_normalize_lever_jobs_basic():
    postings = [
        {
            "text": "Senior Chef",
            "hostedUrl": "https://jobs.lever.co/acme/abc123",
            "categories": {"location": "Boston", "department": "Culinary"},
            "descriptionBody": "<p>Description here</p>",
        }
    ]
    jobs = _normalize_lever_jobs(postings, "Acme")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Senior Chef"
    assert jobs[0]["location"] == "Boston"
    assert jobs[0]["department"] == "Culinary"
    assert jobs[0]["description"] == "<p>Description here</p>"
    assert jobs[0]["extraction_method"] == "api:lever"


def test_normalize_lever_jobs_empty_text_skipped():
    jobs = _normalize_lever_jobs([{"text": "", "hostedUrl": "https://jobs.lever.co/x/1"}], None)
    assert jobs == []


# ── SmartRecruiters ───────────────────────────────────────────────────────────

def test_sr_parse_company_jobs_subdomain():
    assert sr_parse_company("https://jobs.smartrecruiters.com/AcmeCorp") == "AcmeCorp"


def test_sr_parse_company_careers_subdomain():
    assert sr_parse_company("https://careers.smartrecruiters.com/AcmeCorp/jobs") == "AcmeCorp"


def test_sr_parse_company_custom_subdomain():
    assert sr_parse_company("https://acmecorp.smartrecruiters.com/jobs") == "acmecorp"


def test_sr_parse_company_unrecognized():
    assert sr_parse_company("https://example.com/careers") is None


def test_normalize_sr_jobs_basic():
    data = {
        "content": [
            {
                "name": "Restaurant Manager",
                "ref": "https://jobs.smartrecruiters.com/AcmeCorp/123",
                "location": {"city": "Austin", "country": "US"},
                "department": {"label": "Operations"},
            }
        ]
    }
    jobs = _normalize_sr_jobs(data, "Acme Corp")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Restaurant Manager"
    assert jobs[0]["location"] == "Austin, US"
    assert jobs[0]["department"] == "Operations"
    assert jobs[0]["extraction_method"] == "api:smartrecruiters"


# ── SiteAdapter base ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_base_fetch_api_jobs_returns_none():
    """Default SiteAdapter.fetch_api_jobs() must return None (opt-in)."""
    from app.site_adapters.base import SiteAdapter, SiteManifest
    from app.parsers.generic import parse

    class DummyAdapter(SiteAdapter):
        manifest = SiteManifest(family="dummy")
        parser = staticmethod(parse)

    adapter = DummyAdapter()
    result = await adapter.fetch_api_jobs("https://example.com", None, "req-0")
    assert result is None
