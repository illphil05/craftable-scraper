"""API contract test for POST /scrape.

Tests that the endpoint accepts a JSON body (not query params) and returns
the expected response shape. Scraper is mocked so no browser is needed.
Uses httpx.AsyncClient (no lifespan) to avoid the DB startup requirement.
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient


MOCK_RESULT = {
    "jobs": [{"title": "Chef", "company_name": "Acme", "location": "NYC",
               "url": None, "snippet": None, "department": None,
               "description": None, "requirements": None,
               "full_address": None, "maps_url": None, "posted_date": None}],
    "company_name": "Acme",
    "url": "https://boards.greenhouse.io/acme",
    "method": "playwright:greenhouse",
    "adapter_family": "greenhouse",
    "adapter_variant": "greenhouse",
    "jobs_count": 1,
    "error": None,
    "html_sample": None,
    "html_size": None,
    "captured_response_urls": [],
    "captured_response_count": 0,
}

API_KEY = "test-key-abc123"


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("SCRAPER_API_KEY", API_KEY)
    monkeypatch.setenv("SITE_PASSWORD", "pw")

    with patch("app.main.scrape_url", new=AsyncMock(return_value=MOCK_RESULT)):
        with patch("app.main._is_ssrf_url", return_value=False):
            import app.main as main_module
            monkeypatch.setattr(main_module, "API_KEY", API_KEY)
            async with AsyncClient(
                transport=ASGITransport(app=main_module.app),
                base_url="http://test",
            ) as c:
                yield c


async def test_scrape_accepts_json_body(client):
    """POST /scrape must accept URL in JSON body, not as a query param."""
    res = await client.post(
        "/scrape",
        json={"url": "https://boards.greenhouse.io/acme", "timeout": 5000},
        headers={"x-api-key": API_KEY},
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert "jobs" in data
    assert "jobs_count" in data
    assert "method" in data


async def test_scrape_rejects_missing_url(client):
    """POST /scrape with no URL field returns 422 with a detail array."""
    res = await client.post(
        "/scrape",
        json={"timeout": 5000},
        headers={"x-api-key": API_KEY},
    )
    assert res.status_code == 422
    data = res.json()
    assert "detail" in data
    assert isinstance(data["detail"], list), "detail must be a list of validation errors"


async def test_scrape_rejects_no_auth(client):
    """POST /scrape without auth returns 401."""
    res = await client.post("/scrape", json={"url": "https://boards.greenhouse.io/acme"})
    assert res.status_code == 401


async def test_scrape_rejects_bad_url(client):
    """POST /scrape with non-http URL returns 400."""
    res = await client.post(
        "/scrape",
        json={"url": "ftp://bad.example.com"},
        headers={"x-api-key": API_KEY},
    )
    assert res.status_code == 400
