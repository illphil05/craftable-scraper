"""Tests for database layer."""
import os
import tempfile
import pytest
from app import db


@pytest.fixture(autouse=True)
def tmp_db(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        monkeypatch.setattr(db, "DB_PATH", f.name)
        monkeypatch.setattr(db, "_conn", None)
        db.init_db()
        yield f.name
    os.unlink(f.name)


def test_create_and_get_company():
    c = db.create_company("Test Hotel", careers_url="https://example.com/careers", region="northeast")
    assert c["name"] == "Test Hotel"
    assert c["slug"] == "test-hotel"
    assert c["region"] == "northeast"
    assert c["systems_count"] == 0
    assert c["jobs_count"] == 0
    fetched = db.get_company(c["id"])
    assert fetched["name"] == "Test Hotel"


def test_list_companies_search():
    db.create_company("Hilton Hotels")
    db.create_company("Marriott International")
    result = db.list_companies(search="hilton")
    assert result["total"] == 1
    assert result["companies"][0]["name"] == "Hilton Hotels"


def test_update_company():
    c = db.create_company("Old Name")
    updated = db.update_company(c["id"], name="New Name", region="southeast")
    assert updated["name"] == "New Name"
    assert updated["slug"] == "new-name"
    assert updated["region"] == "southeast"


def test_delete_company():
    c = db.create_company("Delete Me")
    db.delete_company(c["id"])
    assert db.get_company(c["id"]) is None


def test_save_scrape():
    c = db.create_company("Scrape Co")
    sid = db.save_scrape(c["id"], "https://example.com", "playwright:paylocity", 10, 5000, None, 50000, False)
    history = db.get_scrape_history(c["id"])
    assert len(history) == 1
    assert history[0]["jobs_found"] == 10


def test_save_and_list_jobs():
    c = db.create_company("Job Co")
    sid = db.save_scrape(c["id"], "https://example.com", "test", 2, 1000, None, None, False)
    db.save_jobs(c["id"], sid, [
        {"title": "Line Cook", "url": "https://example.com/1", "location": "NYC"},
        {"title": "Server", "url": "https://example.com/2", "location": "LA"},
    ])
    result = db.list_jobs(company_id=c["id"])
    assert result["total"] == 2
    assert result["jobs"][0]["company_name"] == "Job Co"


def test_job_deactivation_on_rescrape():
    c = db.create_company("Deactivation Co")
    sid1 = db.save_scrape(c["id"], "https://example.com", "test", 2, 1000, None, None, False)
    db.save_jobs(c["id"], sid1, [
        {"title": "Job A", "url": "https://example.com/a"},
        {"title": "Job B", "url": "https://example.com/b"},
    ])
    # Re-scrape only finds Job A
    sid2 = db.save_scrape(c["id"], "https://example.com", "test", 1, 1000, None, None, False)
    db.save_jobs(c["id"], sid2, [
        {"title": "Job A", "url": "https://example.com/a"},
    ])
    active = db.list_jobs(company_id=c["id"], is_active=True)
    inactive = db.list_jobs(company_id=c["id"], is_active=False)
    assert active["total"] == 1
    assert inactive["total"] == 1
    assert inactive["jobs"][0]["title"] == "Job B"


def test_save_and_get_systems():
    c = db.create_company("Tech Co")
    db.save_systems(c["id"], [
        {"system_name": "Toast POS", "system_id": "toast", "category": "POS", "confidence": 0.8, "matched_keywords": ["toast pos"]},
    ])
    systems = db.get_systems(c["id"])
    assert len(systems) == 1
    assert systems[0]["system_name"] == "Toast POS"
    assert systems[0]["matched_keywords"] == ["toast pos"]


def test_notes():
    c = db.create_company("Notes Co")
    n = db.add_note(c["id"], "Great prospect")
    notes = db.get_notes(c["id"])
    assert len(notes) == 1
    assert notes[0]["note"] == "Great prospect"
    db.delete_note(n["id"])
    assert len(db.get_notes(c["id"])) == 0


def test_stats():
    db.create_company("Stats Co")
    stats = db.get_stats()
    assert stats["companies"] == 1
    assert stats["total_jobs"] == 0


def test_find_company_by_careers_url():
    db.create_company("URL Co", careers_url="https://recruiting.paylocity.com/test")
    found = db.find_company_by_careers_url("https://recruiting.paylocity.com/test")
    assert found["name"] == "URL Co"
    assert db.find_company_by_careers_url("https://nonexistent.com") is None
