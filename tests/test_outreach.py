from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.outreach import build_outreach_import_payload, outreach_config_status, push_to_outreach


def _company(**kwargs) -> dict:
    return {"id": "c1", "name": "Acme", "region": "US", **kwargs}


def _jobs() -> list[dict]:
    return [
        {
            "title": "Chef",
            "url": "https://acme.com/job/1",
            "description": "Make great food",
            "location": "NYC",
        }
    ]


def _payload(**kwargs) -> dict:
    return build_outreach_import_payload(
        _company(**kwargs), "https://acme.com/careers", _jobs()
    )


def _mock_response(status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = "ok"
    return resp


# ── Payload contract ──────────────────────────────────────────────────────────

def test_payload_top_level_fields():
    """Top-level fields outreach depends on are all present."""
    p = _payload()
    assert p["source"] == "craftable_scraper"
    assert p["search_term"] == "scheduled_careers_sweep"
    assert p["careers_url"] == "https://acme.com/careers"
    assert p["region"] == "US"
    assert p["company_id"] == "c1"
    assert isinstance(p["jobs"], list) and len(p["jobs"]) == 1


def test_payload_per_job_fields():
    """Each job has the fields outreach depends on for dedup and display."""
    job = _payload()["jobs"][0]
    assert job["title"] == "Chef"
    assert job["company_name"] == "Acme"
    assert job["source"] == "craftable_scraper"
    assert job["source_url"] == "https://acme.com/job/1"
    assert job["full_description"] == "Make great food"


def test_payload_company_name_fallback():
    """Job company_name inherits from company dict when not set on the job."""
    jobs = [{"title": "Baker", "url": "https://acme.com/job/2"}]
    p = build_outreach_import_payload(_company(), "https://acme.com/careers", jobs)
    assert p["jobs"][0]["company_name"] == "Acme"


def test_payload_job_company_name_preserved():
    """Explicit company_name on job is not overwritten."""
    jobs = [{"title": "Baker", "url": "https://acme.com/job/2", "company_name": "Acme EU"}]
    p = build_outreach_import_payload(_company(), "https://acme.com/careers", jobs)
    assert p["jobs"][0]["company_name"] == "Acme EU"


def test_payload_empty_region():
    """Missing region produces empty string, not None."""
    p = build_outreach_import_payload({"id": "c2", "name": "X"}, "https://x.com", _jobs())
    assert p["region"] == ""


# ── Gate / env behaviour ──────────────────────────────────────────────────────

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

    assert result["ok"] is True
    assert result["skipped"] is False
    assert result["http_status"] == 200
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

    assert result["ok"] is True
    assert result["http_status"] == 200
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["X-API-Key"] == "fallback-key"


@pytest.mark.asyncio
async def test_http_error_returns_status(monkeypatch):
    """Non-2xx response is reflected in the return value."""
    monkeypatch.setenv("PUSH_TO_OUTREACH", "true")
    monkeypatch.setenv("OUTREACH_IMPORT_URL", "https://outreach.example.com/import")
    monkeypatch.setenv("OUTREACH_API_KEY", "key")

    mock_post = AsyncMock(return_value=_mock_response(422))
    with patch("httpx.AsyncClient.post", mock_post):
        result = await push_to_outreach(_payload())

    assert result["ok"] is False
    assert result["skipped"] is False
    assert result["http_status"] == 422


# ── Config status ─────────────────────────────────────────────────────────────

def test_outreach_config_status_all_false(monkeypatch):
    monkeypatch.setenv("PUSH_TO_OUTREACH", "false")
    monkeypatch.setenv("PUSH_MANUAL_SAVES_TO_OUTREACH", "false")
    monkeypatch.delenv("OUTREACH_IMPORT_URL", raising=False)
    monkeypatch.delenv("OUTREACH_API_KEY", raising=False)
    monkeypatch.delenv("SCRAPER_API_KEY", raising=False)
    status = outreach_config_status()
    assert status == {
        "push_to_outreach": False,
        "push_manual_saves_to_outreach": False,
        "import_url_set": False,
        "api_key_set": False,
    }


def test_outreach_config_status_key_set(monkeypatch):
    monkeypatch.setenv("PUSH_TO_OUTREACH", "true")
    monkeypatch.setenv("PUSH_MANUAL_SAVES_TO_OUTREACH", "true")
    monkeypatch.setenv("OUTREACH_IMPORT_URL", "https://outreach.example.com/import")
    monkeypatch.setenv("OUTREACH_API_KEY", "secret")
    status = outreach_config_status()
    assert status["push_to_outreach"] is True
    assert status["push_manual_saves_to_outreach"] is True
    assert status["import_url_set"] is True
    assert status["api_key_set"] is True
    assert "secret" not in str(status)
