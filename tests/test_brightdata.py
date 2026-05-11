"""Tests for the Bright Data REST client (app/brightdata.py) and API proxy."""
import json
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.brightdata import unlock_url, is_configured, BrightDataError


def test_is_configured_false_when_no_key(monkeypatch):
    monkeypatch.delenv("BRIGHTDATA_API_KEY", raising=False)
    assert is_configured() is False


def test_is_configured_true_when_key_set(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "testkey")
    assert is_configured() is True


@pytest.mark.asyncio
async def test_unlock_url_raises_when_no_api_key(monkeypatch):
    monkeypatch.delenv("BRIGHTDATA_API_KEY", raising=False)
    with pytest.raises(BrightDataError, match="BRIGHTDATA_API_KEY"):
        await unlock_url("https://example.com")


@pytest.mark.asyncio
async def test_unlock_url_success(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "testkey")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status_code": 200,
        "headers": {"content-type": "text/html"},
        "body": "<html><body>Jobs content</body></html>",
    }

    with patch("httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await unlock_url("https://example.com/careers")

    assert result["status_code"] == 200
    assert "<html>" in result["body"]
    assert isinstance(result["headers"], dict)


@pytest.mark.asyncio
async def test_unlock_url_server_error_raises(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "testkey")

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch("httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

        with pytest.raises(BrightDataError, match="server error"):
            await unlock_url("https://example.com/careers")


@pytest.mark.asyncio
async def test_unlock_url_uses_correct_zone(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "testkey")
    monkeypatch.setenv("BRIGHTDATA_UNLOCKER_ZONE", "custom_zone1")

    captured_payload = {}

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status_code": 200, "headers": {}, "body": "<html/>"}

    async def fake_post(url, json, headers):
        captured_payload.update(json)
        return mock_response

    with patch("httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post = fake_post
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

        await unlock_url("https://example.com", zone="custom_zone1")

    assert captured_payload["zone"] == "custom_zone1"
    assert captured_payload["url"] == "https://example.com"


# ── _brightdata_api_fallback tests ────────────────────────────────────────────

from app.scraper import _brightdata_api_fallback


class _FakeAdapter:
    class manifest:
        family = "greenhouse"
        variant = "base"

    def api_url_for(self, url):
        return "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true"

    def normalize_api_response(self, data, company_name):
        return [{"title": j["title"], "company_name": company_name or ""} for j in data.get("jobs", [])]


class _NoApiAdapter:
    class manifest:
        family = "generic"
        variant = "base"

    def api_url_for(self, url):
        return None

    def normalize_api_response(self, data, company_name):
        return []


@pytest.mark.asyncio
async def test_bd_api_fallback_skips_when_not_configured(monkeypatch):
    monkeypatch.delenv("BRIGHTDATA_API_KEY", raising=False)
    with patch("app.brightdata.is_configured", return_value=False):
        result = await _brightdata_api_fallback("https://boards.greenhouse.io/acme", "Acme", _FakeAdapter(), "req1")
    assert result is None


@pytest.mark.asyncio
async def test_bd_api_fallback_skips_when_no_api_url(monkeypatch):
    with patch("app.brightdata.is_configured", return_value=True):
        result = await _brightdata_api_fallback("https://example.com/jobs", "Acme", _NoApiAdapter(), "req2")
    assert result is None


@pytest.mark.asyncio
async def test_bd_api_fallback_returns_jobs_on_success():
    payload = {"jobs": [{"title": "Engineer"}, {"title": "Designer"}]}

    with patch("app.brightdata.is_configured", return_value=True), \
         patch("app.brightdata.unlock_url", AsyncMock(return_value={"body": json.dumps(payload)})):
        result = await _brightdata_api_fallback(
            "https://boards.greenhouse.io/acme", "Acme", _FakeAdapter(), "req3"
        )

    assert result is not None
    assert result["jobs_count"] == 2
    assert result["method"] == "brightdata:api:greenhouse"
    assert result["adapter_variant"] == "brightdata_api"
    assert result["error"] is None
    assert result["error_code"] is None


@pytest.mark.asyncio
async def test_bd_api_fallback_zero_jobs_sets_error_code():
    with patch("app.brightdata.is_configured", return_value=True), \
         patch("app.brightdata.unlock_url", AsyncMock(return_value={"body": json.dumps({"jobs": []})})):
        result = await _brightdata_api_fallback(
            "https://boards.greenhouse.io/acme", "Acme", _FakeAdapter(), "req4"
        )

    assert result is not None
    assert result["jobs_count"] == 0
    assert result["error_code"] is None
    assert result["error"] is None


@pytest.mark.asyncio
async def test_bd_api_fallback_returns_none_on_network_error():
    with patch("app.brightdata.is_configured", return_value=True), \
         patch("app.brightdata.unlock_url", AsyncMock(side_effect=Exception("connection timeout"))):
        result = await _brightdata_api_fallback(
            "https://boards.greenhouse.io/acme", "Acme", _FakeAdapter(), "req5"
        )

    assert result is None
