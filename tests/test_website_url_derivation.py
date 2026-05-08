"""Tests for website_url auto-derivation from careers_url (plan item 1)."""
import pytest
from app import db
from app.db import _origin_from_url


# ── Unit tests for _origin_from_url helper ────────────────────────────────────

def test_origin_from_url_standard():
    assert _origin_from_url("https://careers.example.com/jobs") == "https://careers.example.com"


def test_origin_from_url_with_path_and_query():
    assert _origin_from_url("https://boards.greenhouse.io/acme?foo=bar") == "https://boards.greenhouse.io"


def test_origin_from_url_http():
    assert _origin_from_url("http://jobs.example.com/careers") == "http://jobs.example.com"


def test_origin_from_url_no_scheme_returns_original():
    assert _origin_from_url("not-a-url") == "not-a-url"


def test_origin_from_url_empty_returns_original():
    assert _origin_from_url("") == ""


# ── DB-level tests ────────────────────────────────────────────────────────────

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


async def test_create_company_no_auto_derivation_of_website_url():
    """create_company() does NOT auto-derive website_url — callers pass it explicitly."""
    c = await db.create_company(
        "Test Hotel",
        careers_url="https://boards.greenhouse.io/testhotel",
    )
    assert c["website_url"] is None


async def test_create_company_explicit_website_url_not_overridden():
    """Explicit website_url must not be replaced by the derived value."""
    c = await db.create_company(
        "Marriott",
        careers_url="https://jobs.marriott.com/careers",
        website_url="https://www.marriott.com",
    )
    assert c["website_url"] == "https://www.marriott.com"


async def test_create_company_no_careers_url_website_url_is_none():
    """Without careers_url, website_url stays None when not provided."""
    c = await db.create_company("No URL Co")
    assert c["website_url"] is None


async def test_create_company_explicit_website_url_is_stored():
    """Explicit website_url passed to create_company is stored as-is."""
    c = await db.create_company(
        "Constraint Test",
        careers_url="https://jobs.example.com/careers",
        website_url="https://jobs.example.com",
    )
    assert c["website_url"] == "https://jobs.example.com"
    fetched = await db.get_company(c["id"])
    assert fetched["website_url"] == "https://jobs.example.com"
