"""Tests for the Bright Data REST client (app/brightdata.py)."""
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
