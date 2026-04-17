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
            db.execute("""INSERT INTO jobs (id, company_id, scrape_id, title, url, location, department,
                         snippet, description, requirements, full_address, maps_url, posted_date,
                         first_seen, last_seen, is_active) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                      (_uuid(), company_id, scrape_id, j.get("title",""), job_url,
                       j.get("location"), j.get("department"), j.get("snippet"),
                       j.get("description"), reqs_json, j.get("full_address"),
                       j.get("maps_url"), j.get("posted_date"), now, now))

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
