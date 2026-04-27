"""Async SQLite database layer using aiosqlite.

All public functions are async.  A single shared aiosqlite.Connection is
created lazily on first use and reused across requests — aiosqlite serialises
concurrent access internally, making this safe for async FastAPI.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone

import aiosqlite


DB_PATH = os.environ.get("SCRAPER_DB_PATH", "/data/scraper.db")

_conn: aiosqlite.Connection | None = None
_conn_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    """Return (or lazily create) the module-level connection lock.

    Creating the Lock inside a running event loop avoids DeprecationWarnings
    on Python 3.10+ that occur when asyncio primitives are created at import
    time with no running loop.
    """
    global _conn_lock
    if _conn_lock is None:
        _conn_lock = asyncio.Lock()
    return _conn_lock


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


async def get_db() -> aiosqlite.Connection:
    global _conn
    if _conn is None:
        async with _get_lock():
            if _conn is None:
                dir_path = os.path.dirname(DB_PATH)
                if dir_path:
                    os.makedirs(dir_path, exist_ok=True)
                _conn = await aiosqlite.connect(DB_PATH)
                _conn.row_factory = aiosqlite.Row
                await _conn.execute("PRAGMA journal_mode=WAL")
                await _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


async def close_db() -> None:
    """Close the shared connection (called on application shutdown)."""
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


async def init_db() -> None:
    db = await get_db()
    await db.executescript(SCHEMA_SQL)
    await db.commit()


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
    content_hash TEXT,
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
CREATE INDEX IF NOT EXISTS idx_jobs_hash ON jobs(content_hash);
CREATE INDEX IF NOT EXISTS idx_scrape_company ON scrape_history(company_id);
CREATE INDEX IF NOT EXISTS idx_systems_company ON company_systems(company_id);
CREATE INDEX IF NOT EXISTS idx_notes_company ON company_notes(company_id);
"""


def slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _job_content_hash(company_id: str, title: str, location: str | None) -> str:
    """Stable hash used to deduplicate URL-less job listings (item 6)."""
    raw = f"{company_id}|{title.lower().strip()}|{(location or '').lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ── Company CRUD ──────────────────────────────────────────────────────────────

async def create_company(
    name: str,
    careers_url: str | None = None,
    website_url: str | None = None,
    parent_company_name: str | None = None,
    region: str | None = None,
) -> dict:
    db = await get_db()
    now = _now()
    company_id = _uuid()
    slug = slugify(name)
    await db.execute(
        "INSERT INTO companies (id, name, slug, website_url, careers_url, parent_company_name, region, first_seen, last_seen, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (company_id, name, slug, website_url, careers_url, parent_company_name, region, now, now, now),
    )
    await db.commit()
    return await get_company(company_id)


async def get_company(company_id: str) -> dict | None:
    db = await get_db()
    async with db.execute("SELECT * FROM companies WHERE id = ?", (company_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    d = dict(row)
    async with db.execute("SELECT COUNT(*) FROM company_systems WHERE company_id = ?", (company_id,)) as cur:
        d["systems_count"] = (await cur.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM jobs WHERE company_id = ? AND is_active = 1", (company_id,)) as cur:
        d["jobs_count"] = (await cur.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM jobs WHERE company_id = ?", (company_id,)) as cur:
        d["total_jobs"] = (await cur.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM scrape_history WHERE company_id = ?", (company_id,)) as cur:
        d["scrape_count"] = (await cur.fetchone())[0]
    return d


async def update_company(company_id: str, **kwargs) -> dict | None:
    db = await get_db()
    allowed = {"name", "slug", "website_url", "careers_url", "parent_company_name", "region", "notes_text"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if "name" in updates:
        updates["slug"] = slugify(updates["name"])
    if not updates:
        return await get_company(company_id)
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [company_id]
    await db.execute(f"UPDATE companies SET {sets} WHERE id = ?", vals)
    await db.commit()
    return await get_company(company_id)


async def delete_company(company_id: str) -> bool:
    db = await get_db()
    for table, col in [
        ("company_notes", "company_id"),
        ("company_systems", "company_id"),
        ("jobs", "company_id"),
        ("scrape_history", "company_id"),
        ("companies", "id"),
    ]:
        await db.execute(f"DELETE FROM {table} WHERE {col} = ?", (company_id,))
    await db.commit()
    return True


async def list_companies(search: str = "", region: str = "", page: int = 1, limit: int = 50) -> dict:
    db = await get_db()
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
    async with db.execute(sql, params) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    count_params = params[:-2]
    async with db.execute(f"SELECT COUNT(*) FROM companies c {where}", count_params) as cur:
        total = (await cur.fetchone())[0]
    async with db.execute("SELECT region, COUNT(*) as count FROM companies WHERE region IS NOT NULL GROUP BY region ORDER BY count DESC") as cur:
        regions = [dict(r) for r in await cur.fetchall()]
    return {"companies": rows, "total": total, "page": page, "limit": limit, "regions": regions}


async def find_company_by_careers_url(careers_url: str) -> dict | None:
    db = await get_db()
    async with db.execute("SELECT * FROM companies WHERE careers_url = ?", (careers_url,)) as cur:
        row = await cur.fetchone()
    if row:
        return await get_company(dict(row)["id"])
    return None


# ── Scrape History ────────────────────────────────────────────────────────────

async def save_scrape(
    company_id: str | None,
    url: str,
    parser_used: str,
    jobs_found: int,
    elapsed_ms: int,
    error: str | None,
    html_size: int | None,
    deep: bool,
) -> str:
    db = await get_db()
    scrape_id = _uuid()
    await db.execute(
        "INSERT INTO scrape_history (id, company_id, url, parser_used, jobs_found, elapsed_ms, error, html_size, deep, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (scrape_id, company_id, url, parser_used, jobs_found, elapsed_ms, error, html_size, int(deep), _now()),
    )
    if company_id:
        await db.execute("UPDATE companies SET last_seen = ? WHERE id = ?", (_now(), company_id))
    await db.commit()
    return scrape_id


async def get_scrape_history(company_id: str, limit: int = 50) -> list[dict]:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM scrape_history WHERE company_id = ? ORDER BY created_at DESC LIMIT ?",
        (company_id, limit),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def get_recent_scrapes(limit: int = 20) -> list[dict]:
    db = await get_db()
    async with db.execute(
        """SELECT sh.*, c.name as company_name FROM scrape_history sh
           LEFT JOIN companies c ON sh.company_id = c.id
           ORDER BY sh.created_at DESC LIMIT ?""",
        (limit,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


# ── Jobs ──────────────────────────────────────────────────────────────────────

async def save_jobs(company_id: str, scrape_id: str, jobs_data: list[dict]) -> None:
    db = await get_db()
    now = _now()

    # Index existing active jobs by URL then by content_hash (for URL-less jobs)
    async with db.execute(
        "SELECT * FROM jobs WHERE company_id = ? AND is_active = 1", (company_id,)
    ) as cur:
        existing_rows = await cur.fetchall()

    existing_by_url: dict[str, dict] = {}
    existing_by_hash: dict[str, dict] = {}
    for row in existing_rows:
        d = dict(row)
        if d.get("url"):
            existing_by_url[d["url"]] = d
        if d.get("content_hash"):
            existing_by_hash[d["content_hash"]] = d

    seen_urls: set[str | None] = set()
    seen_hashes: set[str] = set()

    for j in jobs_data:
        job_url = j.get("url")
        content_hash = _job_content_hash(company_id, j.get("title", ""), j.get("location"))
        reqs = j.get("requirements")
        reqs_json = json.dumps(reqs) if isinstance(reqs, list) else reqs

        seen_urls.add(job_url)
        seen_hashes.add(content_hash)

        existing = None
        if job_url and job_url in existing_by_url:
            existing = existing_by_url[job_url]
        elif content_hash in existing_by_hash:
            existing = existing_by_hash[content_hash]

        if existing:
            await db.execute(
                """UPDATE jobs SET scrape_id=?, title=?, location=?, department=?, snippet=?,
                   description=COALESCE(?,description), requirements=COALESCE(?,requirements),
                   full_address=COALESCE(?,full_address), maps_url=COALESCE(?,maps_url),
                   posted_date=COALESCE(?,posted_date), last_seen=?, is_active=1, content_hash=?
                   WHERE id=?""",
                (
                    scrape_id, j.get("title", ""), j.get("location"), j.get("department"),
                    j.get("snippet"), j.get("description"), reqs_json,
                    j.get("full_address"), j.get("maps_url"), j.get("posted_date"),
                    now, content_hash, existing["id"],
                ),
            )
        else:
            await db.execute(
                """INSERT INTO jobs (id, company_id, scrape_id, title, url, content_hash,
                   location, department, snippet, description, requirements, full_address,
                   maps_url, posted_date, first_seen, last_seen, is_active)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                (
                    _uuid(), company_id, scrape_id, j.get("title", ""), job_url, content_hash,
                    j.get("location"), j.get("department"), j.get("snippet"),
                    j.get("description"), reqs_json, j.get("full_address"),
                    j.get("maps_url"), j.get("posted_date"), now, now,
                ),
            )

    # Deactivate jobs not seen in this scrape
    for url_key, existing_job in existing_by_url.items():
        if url_key not in seen_urls:
            await db.execute("UPDATE jobs SET is_active = 0 WHERE id = ?", (existing_job["id"],))
    for hash_key, existing_job in existing_by_hash.items():
        if hash_key not in seen_hashes and not existing_job.get("url"):
            await db.execute("UPDATE jobs SET is_active = 0 WHERE id = ?", (existing_job["id"],))

    await db.commit()


async def list_jobs(
    company_id: str | None = None,
    search: str = "",
    department: str = "",
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 50,
) -> dict:
    db = await get_db()
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
    async with db.execute(sql, params) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    count_params = params[:-2]
    async with db.execute(
        f"SELECT COUNT(*) FROM jobs j LEFT JOIN companies c ON j.company_id = c.id {where}",
        count_params,
    ) as cur:
        total = (await cur.fetchone())[0]
    async with db.execute(
        "SELECT DISTINCT department FROM jobs WHERE department IS NOT NULL AND department != '' ORDER BY department"
    ) as cur:
        departments = [dict(r) for r in await cur.fetchall()]
    return {
        "jobs": rows,
        "total": total,
        "page": page,
        "limit": limit,
        "departments": [d["department"] for d in departments],
    }


async def get_job(job_id: str) -> dict | None:
    db = await get_db()
    async with db.execute(
        """SELECT j.*, c.name as company_name FROM jobs j
           LEFT JOIN companies c ON j.company_id = c.id WHERE j.id = ?""",
        (job_id,),
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


# ── Company Systems ───────────────────────────────────────────────────────────

async def save_systems(company_id: str, systems: list[dict]) -> None:
    db = await get_db()
    now = _now()
    await db.execute("DELETE FROM company_systems WHERE company_id = ?", (company_id,))
    for s in systems:
        await db.execute(
            "INSERT INTO company_systems (id, company_id, system_name, system_id, category, confidence, matched_keywords, source, detected_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                _uuid(), company_id, s["system_name"], s["system_id"], s["category"],
                s["confidence"], json.dumps(s.get("matched_keywords", [])), s.get("source", "careers_page"), now,
            ),
        )
    await db.commit()


async def get_systems(company_id: str) -> list[dict]:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM company_systems WHERE company_id = ? ORDER BY category, system_name",
        (company_id,),
    ) as cur:
        rows = await cur.fetchall()
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


async def get_systems_heatmap() -> dict:
    db = await get_db()
    async with db.execute(
        """SELECT cs.system_name, cs.system_id, cs.category, cs.company_id, cs.confidence, c.name as company_name
           FROM company_systems cs JOIN companies c ON cs.company_id = c.id
           ORDER BY cs.category, cs.system_name"""
    ) as cur:
        systems = [dict(r) for r in await cur.fetchall()]
    async with db.execute("SELECT id, name FROM companies ORDER BY name") as cur:
        companies = [dict(r) for r in await cur.fetchall()]
    return {"systems": systems, "companies": companies}


# ── Company Notes ─────────────────────────────────────────────────────────────

async def add_note(company_id: str, note: str) -> dict:
    db = await get_db()
    note_id = _uuid()
    now = _now()
    await db.execute(
        "INSERT INTO company_notes (id, company_id, note, created_at) VALUES (?,?,?,?)",
        (note_id, company_id, note, now),
    )
    await db.commit()
    return {"id": note_id, "company_id": company_id, "note": note, "created_at": now}


async def delete_note(note_id: str) -> bool:
    db = await get_db()
    await db.execute("DELETE FROM company_notes WHERE id = ?", (note_id,))
    await db.commit()
    return True


async def get_notes(company_id: str) -> list[dict]:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM company_notes WHERE company_id = ? ORDER BY created_at DESC",
        (company_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


# ── Stats ─────────────────────────────────────────────────────────────────────

async def get_stats() -> dict:
    from app.parsers import parser_count
    db = await get_db()

    async def _scalar(sql: str) -> int:
        async with db.execute(sql) as cur:
            return (await cur.fetchone())[0]

    return {
        "companies": await _scalar("SELECT COUNT(*) FROM companies"),
        "total_jobs": await _scalar("SELECT COUNT(*) FROM jobs"),
        "active_jobs": await _scalar("SELECT COUNT(*) FROM jobs WHERE is_active = 1"),
        "systems_detected": await _scalar("SELECT COUNT(DISTINCT system_id || company_id) FROM company_systems"),
        "recent_scrapes_24h": await _scalar("SELECT COUNT(*) FROM scrape_history WHERE created_at > datetime('now', '-1 day')"),
        "parsers_available": parser_count(),
    }
