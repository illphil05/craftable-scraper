from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.outreach import build_outreach_import_payload, push_to_outreach


def _payload() -> dict:
    company = {"id": "c1", "name": "Acme", "region": "US"}
    jobs = [{"title": "Chef", "url": "https://acme.com/job/1"}]
    return build_outreach_import_payload(company, "https://acme.com/careers", jobs)


def _mock_response(status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = "ok"
    return resp


@pytest.mark.asyncio
async def test_manual_gate_independent(monkeypatch):
    """Manual gate fires when PUSH_MANUAL_SAVES_TO_OUTREACH=true even if PUSH_TO_OUTREACH=false."""
    monkeypatch.setenv("PUSH_MANUAL_SAVES_TO_OUTREACH", "true")
    monkeypatch.setenv("PUSH_TO_OUTREACH", "false")
    monkeypatch.setenv("OUTREACH_IMPORT_URL", "https://outreach.example.com/import")
    monkeypatch.setenv("OUTREACH_API_KEY", "test-key")

    mock_post = AsyncMock(return_value=_mock_response(200))
    with patch("httpx.AsyncClient.post", mock_post):
        result = await push_to_outreach(_payload(), enabled_env="PUSH_MANUAL_SAVES_TO_OUTREACH")

    assert result == {"ok": True, "skipped": False}
    mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_scheduled_gate_skips_when_false(monkeypatch):
    """Default gate (PUSH_TO_OUTREACH) skips without making any HTTP call."""
    monkeypatch.setenv("PUSH_TO_OUTREACH", "false")

    mock_post = AsyncMock()
    with patch("httpx.AsyncClient.post", mock_post):
        result = await push_to_outreach(_payload())

    assert result == {"ok": False, "skipped": True}
    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_api_key_fallback(monkeypatch):
    """Empty OUTREACH_API_KEY falls back to SCRAPER_API_KEY."""
    monkeypatch.setenv("PUSH_TO_OUTREACH", "true")
    monkeypatch.setenv("OUTREACH_IMPORT_URL", "https://outreach.example.com/import")
    monkeypatch.setenv("OUTREACH_API_KEY", "")
    monkeypatch.setenv("SCRAPER_API_KEY", "fallback-key")

    mock_post = AsyncMock(return_value=_mock_response(200))
    with patch("httpx.AsyncClient.post", mock_post):
        result = await push_to_outreach(_payload())

    assert result == {"ok": True, "skipped": False}
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["X-API-Key"] == "fallback-key"
