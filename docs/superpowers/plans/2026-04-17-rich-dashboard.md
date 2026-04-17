# Rich Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the simple scrape-only UI with a full SPA dashboard backed by SQLite persistence, showing companies, jobs, tech stack detection, scrape history, and an intelligence heatmap.

**Architecture:** SQLite database (host-mounted at `/opt/craftable-scraper/data/scraper.db`) stores companies, jobs, scrape history, and detected tech systems. New API routes in `app/routes.py` serve data to an Alpine.js + Tailwind SPA in `app/ui.py`. Tech stack detection scans scraped HTML for 37 hospitality systems using keyword matching from a ported taxonomy JSON. Existing `/scrape` endpoint unchanged for backward compatibility.

**Tech Stack:** Python 3.12, FastAPI, SQLite (stdlib), Alpine.js 3.14, Tailwind CSS (CDN), Playwright (existing)

**Spec:** `docs/superpowers/specs/2026-04-17-rich-dashboard-design.md`

**Error Log:** Agents MUST append errors and resolutions to `docs/superpowers/plans/error-log.md` so other agents can reference them. Create this file at the start of execution.

---

## Branch Architecture

All work happens on feature branches that merge into a central hub branch. This makes future changes modular — you can modify any layer (DB, API, UI, detection) without touching the others.

```
main
 └── feat/rich-dashboard  (hub branch — all tasks merge here)
      ├── feat/db-layer           (Task 1: app/db.py + tests)
      ├── feat/tech-detection     (Task 2: app/tech_detect.py + taxonomy + tests)
      ├── feat/api-routes         (Task 3: app/routes.py)
      ├── feat/dashboard-ui       (Task 4: app/ui.py rewrite)
      ├── feat/main-integration   (Task 5: app/main.py wiring)
      └── feat/docker-deploy      (Task 6: docker-compose + deploy)
```

**Branch setup (do this first):**
```bash
git checkout main
git pull origin main
git checkout -b feat/rich-dashboard
git push -u origin feat/rich-dashboard
```

**Per-task workflow:**
```bash
# Start task
git checkout feat/rich-dashboard
git pull origin feat/rich-dashboard
git checkout -b feat/<branch-name>

# ... do work, commit ...

# Merge back to hub
git checkout feat/rich-dashboard
git pull origin feat/rich-dashboard
git merge feat/<branch-name> --no-ff -m "merge: <task description>"
git push origin feat/rich-dashboard
```

**Final merge to main** (after Task 7 validation):
```bash
git checkout main
git pull origin main
git merge feat/rich-dashboard --no-ff -m "feat: rich dashboard with persistence, tech detection, and 5-page SPA"
git push origin main
```

**Future changes:** To modify any layer later, branch off `main` (e.g., `fix/db-migration`, `feat/new-parser-ui`). No need to touch the full stack.

---

## Parallel Execution Strategy

```
Time →

Agent A: Task 1 (db.py) ────────────────→ Task 5 (main.py wiring) ──→ Task 7 (integration test)
Agent B: Task 2 (tech_detect.py) ────────→ Task 4 (ui.py - pages 1-3) ─────────────────────────→
Agent C: Task 3 (routes.py) ─────────────→ Task 4 (ui.py - pages 4-5) ─────────────────────────→
                                                                          Task 6 (docker/deploy) →
```

**Dependency gates:**
- Tasks 1, 2 have NO dependencies — start immediately in parallel (own branches)
- Task 3 depends on Task 1 (db.py) and Task 2 (tech_detect.py) — wait for both to merge to hub
- Task 4 depends on Task 3 (API contract must exist) — but can split across agents
- Task 5 depends on Task 1 + Task 3 being merged to hub
- Task 6 depends on all tasks merged to hub
- Task 7 is final validation on `feat/rich-dashboard`

**Agent communication:** All agents share the same git repo. Each agent works on its own feature branch targeting different files. Agents MUST:
1. Branch from `feat/rich-dashboard` before starting each task
2. Commit after each sub-task completes
3. Merge to `feat/rich-dashboard` when task is done
4. Log any errors to `docs/superpowers/plans/error-log.md`
5. If a dependency isn't merged to hub yet, wait and re-check

---

## Task 1: Database Layer (`app/db.py`)

**Files:**
- Create: `app/db.py`
- Test: `tests/test_db.py`

**No dependencies. Can run immediately.**
**Branch:** `feat/db-layer` (from `feat/rich-dashboard`)

- [ ] **Step 0: Create branch**

```bash
git checkout feat/rich-dashboard && git checkout -b feat/db-layer
```

- [ ] **Step 1: Create `app/db.py` with schema and connection management**

```python
"""SQLite database layer for persistent storage."""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone


DB_PATH = os.environ.get("SCRAPER_DB_PATH", "/data/scraper.db")

_conn: sqlite3.Connection | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


def get_db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


def init_db():
    db = get_db()
    db.executescript(SCHEMA_SQL)
    db.commit()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE,
    website_url TEXT,
    careers_url TEXT,
    parent_company_name TEXT,
    region TEXT,
    notes_text TEXT,
    first_seen TEXT,
    last_seen TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS scrape_history (
    id TEXT PRIMARY KEY,
    company_id TEXT REFERENCES companies(id),
    url TEXT NOT NULL,
    parser_used TEXT,
    jobs_found INTEGER DEFAULT 0,
    elapsed_ms INTEGER,
    error TEXT,
    html_size INTEGER,
    deep INTEGER DEFAULT 0,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    company_id TEXT REFERENCES companies(id),
    scrape_id TEXT REFERENCES scrape_history(id),
    title TEXT NOT NULL,
    url TEXT,
    location TEXT,
    department TEXT,
    snippet TEXT,
    description TEXT,
    requirements TEXT,
    full_address TEXT,
    maps_url TEXT,
    posted_date TEXT,
    first_seen TEXT,
    last_seen TEXT,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS company_systems (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    system_name TEXT,
    system_id TEXT,
    category TEXT,
    confidence REAL DEFAULT 0.0,
    matched_keywords TEXT,
    source TEXT,
    detected_at TEXT
);

CREATE TABLE IF NOT EXISTS company_notes (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    note TEXT NOT NULL,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_active);
CREATE INDEX IF NOT EXISTS idx_scrape_company ON scrape_history(company_id);
CREATE INDEX IF NOT EXISTS idx_systems_company ON company_systems(company_id);
CREATE INDEX IF NOT EXISTS idx_notes_company ON company_notes(company_id);
"""


def slugify(name: str) -> str:
    import re
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    return slug.strip('-')


# ── Company CRUD ──

def create_company(name: str, careers_url: str | None = None, website_url: str | None = None,
                   parent_company_name: str | None = None, region: str | None = None) -> dict:
    db = get_db()
    now = _now()
    company_id = _uuid()
    slug = slugify(name)
    db.execute(
        "INSERT INTO companies (id, name, slug, website_url, careers_url, parent_company_name, region, first_seen, last_seen, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (company_id, name, slug, website_url, careers_url, parent_company_name, region, now, now, now)
    )
    db.commit()
    return get_company(company_id)


def get_company(company_id: str) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["systems_count"] = db.execute("SELECT COUNT(*) FROM company_systems WHERE company_id = ?", (company_id,)).fetchone()[0]
    d["jobs_count"] = db.execute("SELECT COUNT(*) FROM jobs WHERE company_id = ? AND is_active = 1", (company_id,)).fetchone()[0]
    d["total_jobs"] = db.execute("SELECT COUNT(*) FROM jobs WHERE company_id = ?", (company_id,)).fetchone()[0]
    d["scrape_count"] = db.execute("SELECT COUNT(*) FROM scrape_history WHERE company_id = ?", (company_id,)).fetchone()[0]
    return d


def update_company(company_id: str, **kwargs) -> dict | None:
    db = get_db()
    allowed = {"name", "slug", "website_url", "careers_url", "parent_company_name", "region", "notes_text"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if "name" in updates:
        updates["slug"] = slugify(updates["name"])
    if not updates:
        return get_company(company_id)
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [company_id]
    db.execute(f"UPDATE companies SET {sets} WHERE id = ?", vals)
    db.commit()
    return get_company(company_id)


def delete_company(company_id: str) -> bool:
    db = get_db()
    db.execute("DELETE FROM company_notes WHERE company_id = ?", (company_id,))
    db.execute("DELETE FROM company_systems WHERE company_id = ?", (company_id,))
    db.execute("DELETE FROM jobs WHERE company_id = ?", (company_id,))
    db.execute("DELETE FROM scrape_history WHERE company_id = ?", (company_id,))
    db.execute("DELETE FROM companies WHERE id = ?", (company_id,))
    db.commit()
    return True


def list_companies(search: str = "", region: str = "", page: int = 1, limit: int = 50) -> dict:
    db = get_db()
    where = "WHERE 1=1"
    params: list = []
    if search:
        where += " AND (c.name LIKE ? OR c.website_url LIKE ? OR c.careers_url LIKE ?)"
        params.extend([f"%{search}%"] * 3)
    if region:
        where += " AND c.region = ?"
        params.append(region)
    offset = (page - 1) * limit

    sql = f"""SELECT c.*,
              (SELECT COUNT(*) FROM company_systems WHERE company_id = c.id) as systems_count,
              (SELECT COUNT(*) FROM jobs WHERE company_id = c.id AND is_active = 1) as jobs_count,
              (SELECT COUNT(*) FROM jobs WHERE company_id = c.id) as total_jobs,
              (SELECT COUNT(*) FROM scrape_history WHERE company_id = c.id) as scrape_count
              FROM companies c {where} ORDER BY c.last_seen DESC LIMIT ? OFFSET ?"""
    params.extend([limit, offset])
    rows = [dict(r) for r in db.execute(sql, params).fetchall()]

    count_params = params[:-2]
    total = db.execute(f"SELECT COUNT(*) FROM companies c {where}", count_params).fetchone()[0]
    regions = [dict(r) for r in db.execute("SELECT region, COUNT(*) as count FROM companies WHERE region IS NOT NULL GROUP BY region ORDER BY count DESC").fetchall()]
    return {"companies": rows, "total": total, "page": page, "limit": limit, "regions": regions}


def find_company_by_careers_url(careers_url: str) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM companies WHERE careers_url = ?", (careers_url,)).fetchone()
    if row:
        return get_company(dict(row)["id"])
    return None


# ── Scrape History ──

def save_scrape(company_id: str | None, url: str, parser_used: str, jobs_found: int,
                elapsed_ms: int, error: str | None, html_size: int | None, deep: bool) -> str:
    db = get_db()
    scrape_id = _uuid()
    db.execute(
        "INSERT INTO scrape_history (id, company_id, url, parser_used, jobs_found, elapsed_ms, error, html_size, deep, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (scrape_id, company_id, url, parser_used, jobs_found, elapsed_ms, error, html_size, int(deep), _now())
    )
    if company_id:
        db.execute("UPDATE companies SET last_seen = ? WHERE id = ?", (_now(), company_id))
    db.commit()
    return scrape_id


def get_scrape_history(company_id: str, limit: int = 50) -> list[dict]:
    db = get_db()
    rows = db.execute("SELECT * FROM scrape_history WHERE company_id = ? ORDER BY created_at DESC LIMIT ?", (company_id, limit)).fetchall()
    return [dict(r) for r in rows]


def get_recent_scrapes(limit: int = 20) -> list[dict]:
    db = get_db()
    rows = db.execute("""SELECT sh.*, c.name as company_name FROM scrape_history sh
                         LEFT JOIN companies c ON sh.company_id = c.id
                         ORDER BY sh.created_at DESC LIMIT ?""", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ── Jobs ──

def save_jobs(company_id: str, scrape_id: str, jobs_data: list[dict]):
    db = get_db()
    now = _now()
    # Mark all existing active jobs for this company as potentially inactive
    existing = {row["url"]: dict(row) for row in db.execute(
        "SELECT * FROM jobs WHERE company_id = ? AND is_active = 1", (company_id,)
    ).fetchall() if row["url"]}

    new_urls = set()
    for j in jobs_data:
        job_url = j.get("url")
        new_urls.add(job_url)
        reqs = j.get("requirements")
        reqs_json = json.dumps(reqs) if isinstance(reqs, list) else reqs

        if job_url and job_url in existing:
            # Update existing job
            db.execute("""UPDATE jobs SET scrape_id=?, title=?, location=?, department=?, snippet=?,
                         description=COALESCE(?,description), requirements=COALESCE(?,requirements),
                         full_address=COALESCE(?,full_address), maps_url=COALESCE(?,maps_url),
                         posted_date=COALESCE(?,posted_date), last_seen=?, is_active=1
                         WHERE id=?""",
                      (scrape_id, j.get("title",""), j.get("location"), j.get("department"),
                       j.get("snippet"), j.get("description"), reqs_json,
                       j.get("full_address"), j.get("maps_url"), j.get("posted_date"),
                       now, existing[job_url]["id"]))
        else:
            # Insert new job
            db.execute("""INSERT INTO jobs (id, company_id, scrape_id, title, url, location, department,
                         snippet, description, requirements, full_address, maps_url, posted_date,
                         first_seen, last_seen, is_active) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                      (_uuid(), company_id, scrape_id, j.get("title",""), job_url,
                       j.get("location"), j.get("department"), j.get("snippet"),
                       j.get("description"), reqs_json, j.get("full_address"),
                       j.get("maps_url"), j.get("posted_date"), now, now))

    # Mark jobs not in this scrape as inactive
    for url, existing_job in existing.items():
        if url not in new_urls:
            db.execute("UPDATE jobs SET is_active = 0 WHERE id = ?", (existing_job["id"],))

    db.commit()


def list_jobs(company_id: str | None = None, search: str = "", department: str = "",
              is_active: bool | None = None, page: int = 1, limit: int = 50) -> dict:
    db = get_db()
    where = "WHERE 1=1"
    params: list = []
    if company_id:
        where += " AND j.company_id = ?"
        params.append(company_id)
    if search:
        where += " AND (j.title LIKE ? OR c.name LIKE ? OR j.location LIKE ?)"
        params.extend([f"%{search}%"] * 3)
    if department:
        where += " AND j.department LIKE ?"
        params.append(f"%{department}%")
    if is_active is not None:
        where += " AND j.is_active = ?"
        params.append(int(is_active))
    offset = (page - 1) * limit

    sql = f"""SELECT j.*, c.name as company_name FROM jobs j
              LEFT JOIN companies c ON j.company_id = c.id
              {where} ORDER BY j.last_seen DESC LIMIT ? OFFSET ?"""
    params.extend([limit, offset])
    rows = [dict(r) for r in db.execute(sql, params).fetchall()]
    count_params = params[:-2]
    total = db.execute(f"SELECT COUNT(*) FROM jobs j LEFT JOIN companies c ON j.company_id = c.id {where}", count_params).fetchone()[0]
    departments = [dict(r) for r in db.execute("SELECT DISTINCT department FROM jobs WHERE department IS NOT NULL AND department != '' ORDER BY department").fetchall()]
    return {"jobs": rows, "total": total, "page": page, "limit": limit, "departments": [d["department"] for d in departments]}


def get_job(job_id: str) -> dict | None:
    db = get_db()
    row = db.execute("""SELECT j.*, c.name as company_name FROM jobs j
                        LEFT JOIN companies c ON j.company_id = c.id WHERE j.id = ?""", (job_id,)).fetchone()
    return dict(row) if row else None


# ── Company Systems ──

def save_systems(company_id: str, systems: list[dict]):
    db = get_db()
    now = _now()
    db.execute("DELETE FROM company_systems WHERE company_id = ?", (company_id,))
    for s in systems:
        db.execute(
            "INSERT INTO company_systems (id, company_id, system_name, system_id, category, confidence, matched_keywords, source, detected_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (_uuid(), company_id, s["system_name"], s["system_id"], s["category"],
             s["confidence"], json.dumps(s.get("matched_keywords", [])), s.get("source", "careers_page"), now)
        )
    db.commit()


def get_systems(company_id: str) -> list[dict]:
    db = get_db()
    rows = db.execute("SELECT * FROM company_systems WHERE company_id = ? ORDER BY category, system_name", (company_id,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("matched_keywords"):
            try:
                d["matched_keywords"] = json.loads(d["matched_keywords"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)
    return result


def get_systems_heatmap() -> dict:
    db = get_db()
    systems = db.execute("""SELECT cs.system_name, cs.system_id, cs.category, cs.company_id, cs.confidence, c.name as company_name
                           FROM company_systems cs JOIN companies c ON cs.company_id = c.id
                           ORDER BY cs.category, cs.system_name""").fetchall()
    companies = db.execute("SELECT id, name FROM companies ORDER BY name").fetchall()
    return {
        "systems": [dict(r) for r in systems],
        "companies": [dict(r) for r in companies],
    }


# ── Company Notes ──

def add_note(company_id: str, note: str) -> dict:
    db = get_db()
    note_id = _uuid()
    now = _now()
    db.execute("INSERT INTO company_notes (id, company_id, note, created_at) VALUES (?,?,?,?)",
              (note_id, company_id, note, now))
    db.commit()
    return {"id": note_id, "company_id": company_id, "note": note, "created_at": now}


def delete_note(note_id: str) -> bool:
    db = get_db()
    db.execute("DELETE FROM company_notes WHERE id = ?", (note_id,))
    db.commit()
    return True


def get_notes(company_id: str) -> list[dict]:
    db = get_db()
    return [dict(r) for r in db.execute("SELECT * FROM company_notes WHERE company_id = ? ORDER BY created_at DESC", (company_id,)).fetchall()]


# ── Stats ──

def get_stats() -> dict:
    db = get_db()
    return {
        "companies": db.execute("SELECT COUNT(*) FROM companies").fetchone()[0],
        "total_jobs": db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
        "active_jobs": db.execute("SELECT COUNT(*) FROM jobs WHERE is_active = 1").fetchone()[0],
        "systems_detected": db.execute("SELECT COUNT(DISTINCT system_id || company_id) FROM company_systems").fetchone()[0],
        "recent_scrapes_24h": db.execute("SELECT COUNT(*) FROM scrape_history WHERE created_at > datetime('now', '-1 day')").fetchone()[0],
        "parsers_available": 8,
    }
```

- [ ] **Step 2: Create `tests/test_db.py`**

```python
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
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/philprobert/craftable-scraper && python -m pytest tests/test_db.py -v`
Expected: All 11 tests PASS.

- [ ] **Step 4: Commit and merge to hub**

```bash
git add app/db.py tests/test_db.py
git commit -m "feat: add SQLite database layer with company/job/system CRUD"
git checkout feat/rich-dashboard
git merge feat/db-layer --no-ff -m "merge: database layer"
git push origin feat/rich-dashboard
```

---

## Task 2: Tech Stack Detection (`app/tech_detect.py`)

**Files:**
- Create: `app/data/tech-taxonomy.json` (copy from outreach)
- Create: `app/tech_detect.py`
- Test: `tests/test_tech_detect.py`

**No dependencies. Can run in parallel with Task 1.**
**Branch:** `feat/tech-detection` (from `feat/rich-dashboard`)

- [ ] **Step 0: Create branch**

```bash
git checkout feat/rich-dashboard && git checkout -b feat/tech-detection
```

- [ ] **Step 1: Copy tech taxonomy from outreach**

```bash
mkdir -p /Users/philprobert/craftable-scraper/app/data
cp /Users/philprobert/craftable-outreach/src/data/tech-taxonomy.json /Users/philprobert/craftable-scraper/app/data/tech-taxonomy.json
```

- [ ] **Step 2: Create `app/tech_detect.py`**

```python
"""Tech stack detection — scans HTML for hospitality system keywords."""
import json
import os
import re

_taxonomy: list[dict] | None = None
TAXONOMY_PATH = os.path.join(os.path.dirname(__file__), "data", "tech-taxonomy.json")


def _load_taxonomy() -> list[dict]:
    global _taxonomy
    if _taxonomy is None:
        with open(TAXONOMY_PATH) as f:
            data = json.load(f)
        _taxonomy = data["systems"]
    return _taxonomy


def detect_systems(html: str, jobs: list[dict] | None = None) -> list[dict]:
    """Scan HTML and job descriptions for tech system keywords.

    Returns list of dicts with: system_id, system_name, category, confidence, matched_keywords, source
    """
    taxonomy = _load_taxonomy()

    # Build combined text corpus
    careers_text = _strip_tags(html).lower()
    job_texts = []
    if jobs:
        for j in jobs:
            parts = [j.get("title", ""), j.get("description", ""), j.get("snippet", "")]
            if isinstance(j.get("requirements"), list):
                parts.extend(j["requirements"])
            elif isinstance(j.get("requirements"), str):
                parts.append(j["requirements"])
            job_texts.append(" ".join(p for p in parts if p).lower())
    all_job_text = " ".join(job_texts)

    detections = []
    for system in taxonomy:
        keywords = system.get("keywords", [])
        if not keywords:
            continue

        matched = []
        source = None
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in careers_text:
                matched.append(kw)
                source = source or "careers_page"
            if kw_lower in all_job_text:
                matched.append(kw)
                source = source or "job_description"

        matched = list(set(matched))
        if not matched:
            continue

        confidence = min(1.0, len(matched) / max(len(keywords), 1))
        detections.append({
            "system_id": system["system_id"],
            "system_name": system["system_name"],
            "category": system["category"],
            "confidence": round(confidence, 2),
            "matched_keywords": matched,
            "source": source,
        })

    detections.sort(key=lambda d: d["confidence"], reverse=True)
    return detections


def _strip_tags(html: str) -> str:
    return re.sub(r'<[^>]+>', ' ', html)
```

- [ ] **Step 3: Create `tests/test_tech_detect.py`**

```python
"""Tests for tech stack detection."""
from app.tech_detect import detect_systems, _load_taxonomy


def test_taxonomy_loads():
    taxonomy = _load_taxonomy()
    assert len(taxonomy) >= 30
    assert all("system_id" in s for s in taxonomy)
    assert all("keywords" in s for s in taxonomy)


def test_detect_toast_in_html():
    html = '<div>We use Toast POS for our restaurant operations</div>'
    results = detect_systems(html)
    toast = [r for r in results if r["system_id"] == "toast"]
    assert len(toast) == 1
    assert toast[0]["category"] == "POS"
    assert toast[0]["confidence"] > 0
    assert "toast pos" in toast[0]["matched_keywords"]


def test_detect_from_job_descriptions():
    html = '<div>Careers page</div>'
    jobs = [
        {"title": "Line Cook", "description": "Experience with Toast POS required"},
        {"title": "Accountant", "description": "Must know QuickBooks Online and Excel"},
    ]
    results = detect_systems(html, jobs)
    ids = {r["system_id"] for r in results}
    assert "toast" in ids
    assert "quickbooks" in ids


def test_no_false_positives():
    html = '<div>We are a great hotel with amazing rooms</div>'
    results = detect_systems(html)
    assert len(results) == 0


def test_confidence_increases_with_more_keywords():
    html = '<div>toast pos toasttab toast point of sale</div>'
    results = detect_systems(html)
    toast = [r for r in results if r["system_id"] == "toast"]
    assert len(toast) == 1
    assert toast[0]["confidence"] > 0.5


def test_spreadsheet_detection():
    html = '<div>Currently tracking inventory in Excel spreadsheets</div>'
    results = detect_systems(html)
    manual = [r for r in results if r["system_id"] == "spreadsheets"]
    assert len(manual) >= 1
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/philprobert/craftable-scraper && python -m pytest tests/test_tech_detect.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit and merge to hub**

```bash
git add app/data/tech-taxonomy.json app/tech_detect.py tests/test_tech_detect.py
git commit -m "feat: add tech stack detection with 37-system hospitality taxonomy"
git checkout feat/rich-dashboard
git merge feat/tech-detection --no-ff -m "merge: tech stack detection"
git push origin feat/rich-dashboard
```

---

## Task 3: API Routes (`app/routes.py`)

**Files:**
- Create: `app/routes.py`

**Depends on: Task 1 (db.py) and Task 2 (tech_detect.py). Wait for both to be merged to hub.**
**Branch:** `feat/api-routes` (from `feat/rich-dashboard`)

- [ ] **Step 1: Create branch from hub (which now has db.py and tech_detect.py)**

```bash
git checkout feat/rich-dashboard
git pull origin feat/rich-dashboard
git checkout -b feat/api-routes
```

- [ ] **Step 2: Create `app/routes.py`**

```python
"""API route handlers for the dashboard."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app import db
from app.tech_detect import detect_systems

router = APIRouter(prefix="/api")


# ── Request/Response models ──

class CompanyCreate(BaseModel):
    name: str
    website_url: str | None = None
    careers_url: str | None = None
    parent_company_name: str | None = None
    region: str | None = None

class CompanyUpdate(BaseModel):
    name: str | None = None
    website_url: str | None = None
    careers_url: str | None = None
    parent_company_name: str | None = None
    region: str | None = None
    notes_text: str | None = None

class NoteCreate(BaseModel):
    note: str

class SaveScrapeRequest(BaseModel):
    company_id: str | None = None
    company_name: str | None = None
    careers_url: str
    parser_used: str
    jobs_found: int
    elapsed_ms: int
    error: str | None = None
    html_size: int | None = None
    deep: bool = False
    jobs: list[dict] = []
    html: str = ""


# ── Company routes ──

@router.get("/companies")
def list_companies(search: str = "", region: str = "", page: int = 1, limit: int = 50):
    return db.list_companies(search=search, region=region, page=page, limit=limit)


@router.get("/companies/{company_id}")
def get_company(company_id: str):
    c = db.get_company(company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    c["systems"] = db.get_systems(company_id)
    c["notes"] = db.get_notes(company_id)
    return c


@router.post("/companies")
def create_company(body: CompanyCreate):
    return db.create_company(
        name=body.name, website_url=body.website_url, careers_url=body.careers_url,
        parent_company_name=body.parent_company_name, region=body.region
    )


@router.put("/companies/{company_id}")
def update_company(company_id: str, body: CompanyUpdate):
    c = db.update_company(company_id, **body.model_dump(exclude_none=True))
    if not c:
        raise HTTPException(404, "Company not found")
    return c


@router.delete("/companies/{company_id}")
def delete_company(company_id: str):
    db.delete_company(company_id)
    return {"ok": True}


# ── Company sub-resources ──

@router.get("/companies/{company_id}/jobs")
def company_jobs(company_id: str, is_active: bool | None = None, page: int = 1, limit: int = 50):
    return db.list_jobs(company_id=company_id, is_active=is_active, page=page, limit=limit)


@router.get("/companies/{company_id}/scrapes")
def company_scrapes(company_id: str):
    return db.get_scrape_history(company_id)


@router.get("/companies/{company_id}/systems")
def company_systems(company_id: str):
    return db.get_systems(company_id)


@router.post("/companies/{company_id}/notes")
def add_note(company_id: str, body: NoteCreate):
    return db.add_note(company_id, body.note)


@router.delete("/companies/{company_id}/notes/{note_id}")
def delete_note(company_id: str, note_id: str):
    db.delete_note(note_id)
    return {"ok": True}


# ── Jobs ──

@router.get("/jobs")
def list_jobs(search: str = "", company_id: str = "", department: str = "",
              is_active: bool | None = None, page: int = 1, limit: int = 50):
    return db.list_jobs(company_id=company_id or None, search=search, department=department,
                        is_active=is_active, page=page, limit=limit)


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    j = db.get_job(job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return j


# ── Dashboard data ──

@router.get("/stats")
def get_stats():
    return db.get_stats()


@router.get("/systems-heatmap")
def systems_heatmap():
    return db.get_systems_heatmap()


# ── Save scrape results to DB ──

@router.post("/save-scrape")
def save_scrape(body: SaveScrapeRequest):
    """Save scrape results to the database. Called after a successful /scrape."""
    company_id = body.company_id

    # Auto-find or create company
    if not company_id and body.careers_url:
        existing = db.find_company_by_careers_url(body.careers_url)
        if existing:
            company_id = existing["id"]
        elif body.company_name:
            c = db.create_company(name=body.company_name, careers_url=body.careers_url)
            company_id = c["id"]

    if not company_id:
        raise HTTPException(400, "No company_id and could not auto-resolve company")

    # Save scrape history
    scrape_id = db.save_scrape(
        company_id=company_id, url=body.careers_url, parser_used=body.parser_used,
        jobs_found=body.jobs_found, elapsed_ms=body.elapsed_ms, error=body.error,
        html_size=body.html_size, deep=body.deep
    )

    # Save jobs
    if body.jobs:
        db.save_jobs(company_id, scrape_id, body.jobs)

    # Detect and save tech systems
    if body.html:
        systems = detect_systems(body.html, body.jobs)
        if systems:
            db.save_systems(company_id, systems)

    company = db.get_company(company_id)
    return {"ok": True, "company_id": company_id, "scrape_id": scrape_id, "company": company}
```

- [ ] **Step 3: Commit and merge to hub**

```bash
git add app/routes.py
git commit -m "feat: add API routes for companies, jobs, systems, and scrape saving"
git checkout feat/rich-dashboard
git merge feat/api-routes --no-ff -m "merge: API routes"
git push origin feat/rich-dashboard
```

---

## Task 4: Dashboard UI (`app/ui.py` rewrite)

**Files:**
- Rewrite: `app/ui.py`

**Depends on: Task 3 (routes.py — API contract). This is the largest task. Split across agents if possible: one agent does pages 1-3 (overview, company detail, job listings), another does pages 4-5 (intelligence, scrape).**
**Branch:** `feat/dashboard-ui` (from `feat/rich-dashboard`)

- [ ] **Step 0: Create branch from hub**

```bash
git checkout feat/rich-dashboard
git pull origin feat/rich-dashboard
git checkout -b feat/dashboard-ui
```

- [ ] **Step 1: Read the current `app/ui.py` to understand structure**

Read: `app/ui.py`

- [ ] **Step 2: Rewrite `app/ui.py` with the full SPA dashboard**

The complete file is too large to include inline (~2000 lines). The agent MUST build it following these exact specifications:

**Framework:** Alpine.js 3.14 (CDN), Tailwind CSS (CDN), Inter font (Google Fonts). Same pattern as craftable-outreach's `dashboard.html`.

**Functions to export:**
- `login_page(error: bool) -> str` — unchanged from current
- `scraper_page() -> str` — returns the full SPA HTML

**HTML structure:**
```
<body x-data="app()" x-init="init()">
  <nav> — sticky top bar with: "Craftable Scraper" brand, page buttons (Overview, Jobs, Intelligence, Scrape), sign out
  <main>
    Page 1: Overview (#/overview)
    Page 2: Company Detail (#/company/:id)
    Page 3: Job Listings (#/jobs)
    Page 4: Intelligence (#/intelligence)
    Page 5: Scrape (#/scrape)
  </main>
</body>
```

**Alpine.js `app()` state:**
```javascript
{
  page: 'overview',         // current page
  companyId: null,          // for company detail
  companyTab: 'jobs',       // sub-tab on company page

  // Overview
  stats: null,
  companies: [],
  companiesTotal: 0,
  companiesSearch: '',
  companiesRegion: '',
  regions: [],

  // Company detail
  company: null,
  companyJobs: [],
  companyScrapes: [],
  companyNotes: [],

  // Jobs page
  allJobs: [],
  jobsTotal: 0,
  jobsSearch: '',
  jobsDept: '',
  jobsCompany: '',
  jobsActive: null,
  departments: [],
  selectedJob: null,       // for slide-over

  // Intelligence
  heatmap: null,

  // Scrape page
  scrapeUrl: '',
  scrapeCompany: '',
  scrapeTimeout: 30000,
  scrapeDeep: false,
  scrapeDebug: false,
  scrapeLoading: false,
  scrapeResult: null,
  scrapeError: '',
  recentScrapes: [],

  loading: false,
}
```

**API calls:** All fetch calls go to `/api/...` endpoints defined in Task 3. Use `credentials: 'same-origin'` to pass session cookie.

**Page 1 — Overview:**
- 6 stat cards: Companies, Total Jobs, Active Jobs, Systems Detected, Recent Scrapes (24h), Parsers (8)
- Search input + region dropdown filter
- Companies table: Name (blue, clickable → `navigate('company', id)`), Region (badge), Jobs (active/total), Systems, Last Scraped (date), Actions (re-scrape icon button)
- Load via `GET /api/stats` and `GET /api/companies?search=&region=`

**Page 2 — Company Detail:**
- Back button → overview
- Header card: name, website (link), careers URL (link), parent company, region, first/last seen
- Edit button → inline modal to update company fields via `PUT /api/companies/:id`
- 4 tabs:
  - **Jobs tab:** table with title, location, department, posted date, status badge (active=green, inactive=gray). Click row → slide-over panel on right with full description, requirements list, address, maps link.
  - **Tech Stack tab:** list of detected systems. Each row: system name, category (color-coded badge), confidence bar (0-100%), matched keywords as small tags.
  - **Scrape History tab:** table with date, parser, jobs found, elapsed ms, deep flag, error. Re-scrape button at top.
  - **Notes tab:** list of notes with timestamp. Add note form (textarea + submit). Delete button per note.

**Page 3 — Job Listings:**
- Search bar, company dropdown, department dropdown, active/inactive toggle
- Table: Title, Company (clickable → company detail), Location, Department, Posted Date, Status
- Click row → slide-over with full details
- Pagination

**Page 4 — Intelligence:**
- Tech stack heatmap: table with systems as rows (grouped by category), companies as columns. Cell colored if system detected (opacity = confidence). Click company header → company detail.
- Below: hiring trends section. Companies with job count changes. Green up/red down/gray dash indicators.
- Load via `GET /api/systems-heatmap`

**Page 5 — Scrape:**
- Same form fields as current UI (URL, company name, timeout, deep, debug)
- Results table inline (same as current)
- After scrape: "Save to Company" button. If company found by careers URL, shows "Link to [name]". If new, shows "Create new company" with name pre-filled.
- Calls `POST /scrape` then `POST /api/save-scrape` on save.
- Recent scrapes list from DB via `GET /api/stats` (or dedicated recent-scrapes endpoint)

**Styling rules:**
- Light mode: `bg-slate-50` body, `bg-white` cards, `border-slate-200` borders
- Blue-600 accent for primary actions, links, active states
- Same card style as current: `rounded-2xl shadow-sm border border-slate-200 p-6`
- Stat cards: `rounded-xl border border-slate-200 p-4`
- Tables: `text-sm`, `divide-y divide-slate-100` tbody, `bg-slate-50` thead
- Badges: `inline-flex px-2 py-0.5 rounded-full text-xs font-medium`
- Match craftable-outreach dashboard styling exactly (see `/Users/philprobert/craftable-outreach/src/batch/dashboard.html` for reference)

**Hash routing:**
```javascript
navigate(page, id) {
  this.page = page;
  if (id) this.companyId = id;
  window.location.hash = id ? `#/${page}/${id}` : `#/${page}`;
  this.loadPage();
},
init() {
  const hash = window.location.hash.slice(2) || 'overview';
  const parts = hash.split('/');
  this.page = parts[0] || 'overview';
  if (parts[1]) this.companyId = parts[1];
  this.loadPage();
}
```

- [ ] **Step 3: Verify the login page still works**

The `login_page()` function and `LOGIN_HTML`/`ERROR_BANNER` constants must remain unchanged.

- [ ] **Step 4: Commit and merge to hub**

```bash
git add app/ui.py
git commit -m "feat: rewrite dashboard UI with 5-page SPA (overview, company, jobs, intelligence, scrape)"
git checkout feat/rich-dashboard
git merge feat/dashboard-ui --no-ff -m "merge: dashboard UI rewrite"
git push origin feat/rich-dashboard
```

---

## Task 5: Main.py Integration

**Files:**
- Modify: `app/main.py`

**Depends on: Task 1 (db.py) and Task 3 (routes.py) merged to hub**
**Branch:** `feat/main-integration` (from `feat/rich-dashboard`)

- [ ] **Step 1: Create branch from hub**

```bash
git checkout feat/rich-dashboard
git pull origin feat/rich-dashboard
git checkout -b feat/main-integration
```

- [ ] **Step 2: Modify `app/main.py` to wire up DB and routes**

Add these changes to the existing `app/main.py`:

1. Add imports at top:
```python
from app.db import init_db
from app.routes import router as api_router
```

2. After `app = FastAPI(...)` line, add:
```python
app.include_router(api_router)

@app.on_event("startup")
def startup():
    init_db()
```

3. Add auth middleware so all `/api/*` routes require auth. Add this after the `_require_auth` function:
```python
from fastapi import Depends
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            api_key = request.headers.get("x-api-key", "")
            if not (api_key == API_KEY or _is_authed(request)):
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)

app.add_middleware(AuthMiddleware)
```

4. Update the `/scrape` endpoint to also return a `scrape_id` field when results are saved. **Do NOT change the response model** — the save happens client-side via a separate `/api/save-scrape` call.

- [ ] **Step 3: Verify existing endpoints still work**

Run: `curl -s http://localhost:3010/health` — should return `{"status":"ok",...}`

- [ ] **Step 4: Commit and merge to hub**

```bash
git add app/main.py
git commit -m "feat: wire up database init and API routes in main.py"
git checkout feat/rich-dashboard
git merge feat/main-integration --no-ff -m "merge: main.py integration"
git push origin feat/rich-dashboard
```

---

## Task 6: Docker & Deploy

**Files:**
- Modify: `docker-compose.yml`
- Modify: `Dockerfile` (add `app/data/` to COPY)

**Depends on: All previous tasks merged to hub.**
**Branch:** `feat/docker-deploy` (from `feat/rich-dashboard`)

- [ ] **Step 0: Create branch from hub**

```bash
git checkout feat/rich-dashboard
git pull origin feat/rich-dashboard
git checkout -b feat/docker-deploy
```

- [ ] **Step 1: Update `docker-compose.yml` to add host volume mount**

```yaml
services:
  scraper:
    build: .
    container_name: craftable-scraper
    expose:
      - "3010"
    environment:
      - SCRAPER_API_KEY=craftable-scraper-2026
      - SITE_PASSWORD=Miles2026
      - SCRAPER_DB_PATH=/data/scraper.db
    volumes:
      - /opt/craftable-scraper/data:/data
    restart: unless-stopped
    networks:
      - default
      - proxy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.craftable-scraper.rule=Host(`scraper.myrtle.cloud`)"
      - "traefik.http.routers.craftable-scraper.entrypoints=websecure"
      - "traefik.http.routers.craftable-scraper.tls.certresolver=letsencrypt"
      - "traefik.http.services.craftable-scraper.loadbalancer.server.port=3010"
      - "traefik.docker.network=proxy"

networks:
  proxy:
    external: true
```

- [ ] **Step 2: Update `Dockerfile` to copy `app/data/` directory**

Change line `COPY app/ ./app/` — this already copies the entire `app/` directory including `app/data/tech-taxonomy.json`, so no change needed. Verify this is the case.

- [ ] **Step 3: Create data directory on VPS**

Use Hostinger MCP or SSH to create: `mkdir -p /opt/craftable-scraper/data`

Since we can't SSH directly, we'll handle this through the deploy — the docker-compose `volumes` directive will fail gracefully if the host dir doesn't exist, so we need to create it. Use a one-time init container or create it manually.

Add to docker-compose.yml an init service:

```yaml
services:
  init:
    image: alpine
    command: sh -c "mkdir -p /host-data && echo 'Data dir ready'"
    volumes:
      - /opt/craftable-scraper/data:/host-data
    restart: "no"
```

Actually, Docker will auto-create the host directory if it doesn't exist. So no init service needed. Remove this step.

- [ ] **Step 4: Commit and merge to hub**

```bash
git add docker-compose.yml
git commit -m "feat: add persistent volume mount for SQLite database"
git checkout feat/rich-dashboard
git merge feat/docker-deploy --no-ff -m "merge: docker config and deploy"
git push origin feat/rich-dashboard
```

- [ ] **Step 5: Merge hub to main and deploy**

```bash
git checkout main
git pull origin main
git merge feat/rich-dashboard --no-ff -m "feat: rich dashboard with persistence, tech detection, and 5-page SPA"
git push origin main
```

- [ ] **Step 6: Deploy to Hostinger**

1. Delete old project: `VPS_deleteProjectV1(1334676, "craftable-scraper")`
2. Wait 25 seconds
3. Create new project: `VPS_createNewProjectV1(1334676, "craftable-scraper", "https://github.com/illphil05/craftable-scraper", "SCRAPER_API_KEY=craftable-scraper-2026\nSITE_PASSWORD=Miles2026\nSCRAPER_DB_PATH=/data/scraper.db")`
4. Wait 70 seconds for build
5. Restart Traefik: `VPS_restartProjectV1(1334676, "traefik")`
6. Wait 15 seconds
7. Verify: `curl -s https://scraper.myrtle.cloud/health`

---

## Task 7: Integration Test & Validation

**Depends on: Task 6 (deployed successfully from main)**

- [ ] **Step 1: Verify health endpoint**

```bash
curl -s https://scraper.myrtle.cloud/health
```
Expected: `{"status":"ok","service":"craftable-scraper","version":"1.1.0"}`

- [ ] **Step 2: Verify dashboard loads**

```bash
curl -s -o /dev/null -w "%{http_code}" https://scraper.myrtle.cloud/ -b "scraper_session=<SESSION_VALUE>"
```
Expected: 200

- [ ] **Step 3: Test full scrape + save flow via API**

```bash
# Scrape Avion Hospitality
curl -s -X POST https://scraper.myrtle.cloud/scrape \
  -H "Content-Type: application/json" \
  -H "X-API-Key: craftable-scraper-2026" \
  -d '{"url":"https://recruiting.paylocity.com/recruiting/jobs/All/27d4ca3b-9889-4ede-86a9-59181bb27983/Avion-Hospitality","timeout":45000}'

# Save results to DB (using response data from above)
curl -s -X POST https://scraper.myrtle.cloud/api/save-scrape \
  -H "Content-Type: application/json" \
  -H "X-API-Key: craftable-scraper-2026" \
  -d '{"company_name":"Avion Hospitality","careers_url":"https://recruiting.paylocity.com/recruiting/jobs/All/27d4ca3b-9889-4ede-86a9-59181bb27983/Avion-Hospitality","parser_used":"playwright:paylocity","jobs_found":228,"elapsed_ms":15000,"html_size":50000,"jobs":[{"title":"Line Cook","url":"https://example.com/1","location":"Oklahoma, OK"}],"html":"<div>Experience with Toast POS required</div>"}'
```

- [ ] **Step 4: Verify stats endpoint**

```bash
curl -s https://scraper.myrtle.cloud/api/stats \
  -H "X-API-Key: craftable-scraper-2026"
```
Expected: `{"companies":1,"total_jobs":1,"active_jobs":1,...}`

- [ ] **Step 5: Verify companies endpoint**

```bash
curl -s https://scraper.myrtle.cloud/api/companies \
  -H "X-API-Key: craftable-scraper-2026"
```
Expected: List with Avion Hospitality, systems_count > 0 (Toast detected)

- [ ] **Step 6: Verify heatmap endpoint**

```bash
curl -s https://scraper.myrtle.cloud/api/systems-heatmap \
  -H "X-API-Key: craftable-scraper-2026"
```
Expected: Systems array with toast entry linked to Avion Hospitality

- [ ] **Step 7: Test via browser UI**

Navigate to https://scraper.myrtle.cloud, login with Miles2026, verify:
1. Overview page shows stat cards and Avion Hospitality in table
2. Click Avion → company detail with jobs, tech stack, scrape history tabs
3. Jobs page shows job listings
4. Intelligence page shows heatmap
5. Scrape page works (scrape + save to company)

---

## Error Log Protocol

All agents MUST follow this protocol:

1. **Before starting any task:** Create `docs/superpowers/plans/error-log.md` if it doesn't exist
2. **On any error:** Append to error log with format:
```markdown
### [TIMESTAMP] Agent [N] — Task [N] Step [N]
**Error:** <error message>
**Root cause:** <diagnosis>
**Fix:** <what was done>
**Status:** RESOLVED / BLOCKED
```
3. **Before starting a dependent task:** Read the error log. If any BLOCKED entries exist for dependencies, wait or adapt.
4. **On git conflicts:** Resolve by pulling latest, rebasing, and re-applying changes. Log the conflict.
