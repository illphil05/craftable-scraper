"""Tests for app/intelligence: detect_systems, extract_bullets, daily_digest endpoint."""
from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ── detect_systems ─────────────────────────────────────────────────────────

def test_detect_systems_finds_known_system():
    from app.intelligence.extractor import detect_systems
    text = "We use Toast POS for our restaurant operations."
    result = detect_systems(text)
    assert "Toast" in result


def test_detect_systems_word_boundary():
    """'Excel' must not match 'excellent communication skills'."""
    from app.intelligence.extractor import detect_systems
    text = "Excellent communication skills required. Excellence in teamwork."
    result = detect_systems(text)
    assert not any("excel" in s.lower() for s in result)


def test_detect_systems_case_insensitive():
    from app.intelligence.extractor import detect_systems
    text = "Experience with OPERA pms required."
    result = detect_systems(text)
    assert any(s.lower() == "opera" for s in result)


def test_detect_systems_empty_text():
    from app.intelligence.extractor import detect_systems
    assert detect_systems("") == []


def test_detect_systems_no_duplicates():
    from app.intelligence.extractor import detect_systems
    text = "Toast POS system. We love Toast. Toast is great."
    result = detect_systems(text)
    lower = [s.lower() for s in result]
    assert len(lower) == len(set(lower))


# ── extract_bullets ─────────────────────────────────────────────────────────

async def test_extract_bullets_returns_empty_without_api_key(monkeypatch):
    """Returns [] when ANTHROPIC_API_KEY is not set."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from app.intelligence.extractor import extract_bullets
    bullets = await extract_bullets("Director of Finance managing $10M P&L.")
    assert bullets == []


async def test_extract_bullets_returns_high_confidence(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    fake_response = json.dumps([
        {"category": "Cost Control", "bullet": "Manages P&L for 3 properties", "confidence": "high"},
        {"category": "Financial Reporting", "bullet": "QuickBooks reconciliation", "confidence": "low"},
    ])

    mock_content_item = MagicMock()
    mock_content_item.text = fake_response
    mock_response = MagicMock()
    mock_response.content = [mock_content_item]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("app.intelligence.extractor._get_client", return_value=mock_client):
        from app.intelligence import extractor
        # Reset module-level client so _get_client() is called fresh
        original = extractor._client
        extractor._client = None
        try:
            bullets = await extractor.extract_bullets(
                "Director of Finance managing $10M P&L across properties."
            )
        finally:
            extractor._client = original

    assert any(b["confidence"] == "high" for b in bullets)


async def test_extract_bullets_malformed_json_returns_empty(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_content_item = MagicMock()
    mock_content_item.text = "not valid json at all"
    mock_response = MagicMock()
    mock_response.content = [mock_content_item]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("app.intelligence.extractor._get_client", return_value=mock_client):
        from app.intelligence import extractor
        original = extractor._client
        extractor._client = None
        try:
            bullets = await extractor.extract_bullets("some text")
        finally:
            extractor._client = original

    assert bullets == []


# ── daily_digest endpoint ───────────────────────────────────────────────────

async def test_daily_digest_keys(monkeypatch, tmp_path):
    """Verify the digest returns expected keys and auth is honoured."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("SCRAPER_API_KEY", "test-api-key")
    monkeypatch.setenv("SCRAPER_DB_PATH", str(db_file))

    from app import db as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_file))
    monkeypatch.setattr(db_mod, "_conn", None)
    if db_mod._conn_lock is not None:
        monkeypatch.setattr(db_mod, "_conn_lock", None)
    await db_mod.init_db()

    import app.main as main_module
    from app.main import app as test_app
    monkeypatch.setattr(main_module, "API_KEY", "test-api-key")

    try:
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            resp = await client.get(
                "/api/intelligence/digest/daily",
                headers={"x-api-key": "test-api-key"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "unenriched_companies_24h" in data
        assert "new_roles_24h" in data
        assert "hiring_surge" in data
        assert "new_companies_24h" not in data, "old key should no longer exist"
    finally:
        if db_mod._conn is not None:
            await db_mod._conn.close()
            db_mod._conn = None
