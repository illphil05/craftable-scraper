"""Tests for the async database layer."""
import os
import pytest
from app import db


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


async def test_create_and_get_company():
    c = await db.create_company("Test Hotel", careers_url="https://example.com/careers", region="northeast")
    assert c["name"] == "Test Hotel"
    assert c["slug"] == "test-hotel"
    assert c["region"] == "northeast"
    assert c["systems_count"] == 0
    assert c["jobs_count"] == 0
    fetched = await db.get_company(c["id"])
    assert fetched["name"] == "Test Hotel"


async def test_list_companies_search():
    await db.create_company("Hilton Hotels")
    await db.create_company("Marriott International")
    result = await db.list_companies(search="hilton")
    assert result["total"] == 1
    assert result["companies"][0]["name"] == "Hilton Hotels"


async def test_update_company():
    c = await db.create_company("Old Name")
    updated = await db.update_company(c["id"], name="New Name", region="southeast")
    assert updated["name"] == "New Name"
    assert updated["slug"] == "new-name"
    assert updated["region"] == "southeast"


async def test_delete_company():
    c = await db.create_company("Delete Me")
    await db.delete_company(c["id"])
    assert await db.get_company(c["id"]) is None


async def test_save_scrape():
    c = await db.create_company("Scrape Co")
    sid = await db.save_scrape(c["id"], "https://example.com", "playwright:paylocity", 10, 5000, None, 50000, False)
    history = await db.get_scrape_history(c["id"])
    assert len(history) == 1
    assert history[0]["jobs_found"] == 10


async def test_save_and_list_jobs():
    c = await db.create_company("Job Co")
    sid = await db.save_scrape(c["id"], "https://example.com", "test", 2, 1000, None, None, False)
    await db.save_jobs(c["id"], sid, [
        {"title": "Line Cook", "url": "https://example.com/1", "location": "NYC"},
        {"title": "Server", "url": "https://example.com/2", "location": "LA"},
    ])
    result = await db.list_jobs(company_id=c["id"])
    assert result["total"] == 2
    assert result["jobs"][0]["company_name"] == "Job Co"


async def test_job_deactivation_on_rescrape():
    c = await db.create_company("Deactivation Co")
    sid1 = await db.save_scrape(c["id"], "https://example.com", "test", 2, 1000, None, None, False)
    await db.save_jobs(c["id"], sid1, [
        {"title": "Job A", "url": "https://example.com/a"},
        {"title": "Job B", "url": "https://example.com/b"},
    ])
    # Re-scrape only finds Job A
    sid2 = await db.save_scrape(c["id"], "https://example.com", "test", 1, 1000, None, None, False)
    await db.save_jobs(c["id"], sid2, [
        {"title": "Job A", "url": "https://example.com/a"},
    ])
    active = await db.list_jobs(company_id=c["id"], is_active=True)
    inactive = await db.list_jobs(company_id=c["id"], is_active=False)
    assert active["total"] == 1
    assert inactive["total"] == 1
    assert inactive["jobs"][0]["title"] == "Job B"


async def test_url_less_job_deduplication_by_hash():
    """Jobs without URLs should be deduplicated via content_hash (item 6)."""
    c = await db.create_company("Hash Co")
    sid1 = await db.save_scrape(c["id"], "https://example.com", "test", 1, 500, None, None, False)
    await db.save_jobs(c["id"], sid1, [
        {"title": "Sous Chef", "url": None, "location": "Chicago, IL"},
    ])
    sid2 = await db.save_scrape(c["id"], "https://example.com", "test", 1, 500, None, None, False)
    await db.save_jobs(c["id"], sid2, [
        {"title": "Sous Chef", "url": None, "location": "Chicago, IL"},
    ])
    result = await db.list_jobs(company_id=c["id"])
    # Same title+location should not create a duplicate row
    assert result["total"] == 1


async def test_save_and_get_systems():
    c = await db.create_company("Tech Co")
    await db.save_systems(c["id"], [
        {"system_name": "Toast POS", "system_id": "toast", "category": "POS", "confidence": 0.8, "matched_keywords": ["toast pos"]},
    ])
    systems = await db.get_systems(c["id"])
    assert len(systems) == 1
    assert systems[0]["system_name"] == "Toast POS"
    assert systems[0]["matched_keywords"] == ["toast pos"]


async def test_notes():
    c = await db.create_company("Notes Co")
    n = await db.add_note(c["id"], "Great prospect")
    notes = await db.get_notes(c["id"])
    assert len(notes) == 1
    assert notes[0]["note"] == "Great prospect"
    await db.delete_note(n["id"])
    assert len(await db.get_notes(c["id"])) == 0


async def test_stats():
    from app.parsers import parser_count
    await db.create_company("Stats Co")
    stats = await db.get_stats()
    assert stats["companies"] == 1
    assert stats["total_jobs"] == 0
    assert stats["parsers_available"] == parser_count()


async def test_find_company_by_careers_url():
    await db.create_company("URL Co", careers_url="https://recruiting.paylocity.com/test")
    found = await db.find_company_by_careers_url("https://recruiting.paylocity.com/test")
    assert found["name"] == "URL Co"
    assert await db.find_company_by_careers_url("https://nonexistent.com") is None
