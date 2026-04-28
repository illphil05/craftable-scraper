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
    # Pre-flight: if jobs table exists without content_hash, add it before
    # executescript tries to create idx_jobs_hash on that column.
    async with db.execute("PRAGMA table_info(jobs)") as cur:
        existing_cols = {row[1] for row in await cur.fetchall()}
    if existing_cols and "content_hash" not in existing_cols:
        await db.execute("ALTER TABLE jobs ADD COLUMN content_hash TEXT")
        await db.commit()
    await db.executescript(SCHEMA_SQL)
    await _run_migrations(db)
    await db.commit()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE,
    website_url TEXT,
    careers_url TEXT,
    careers_source TEXT,
    site_family TEXT,
    site_variant TEXT,
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
    adapter_family TEXT,
    adapter_variant TEXT,
    jobs_found INTEGER DEFAULT 0,
    elapsed_ms INTEGER,
    error TEXT,
    html_size INTEGER,
    artifact_refs TEXT,
    deep INTEGER DEFAULT 0,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    company_id TEXT REFERENCES companies(id),
    scrape_id TEXT REFERENCES scrape_history(id),
    title TEXT NOT NULL,
    canonical_title TEXT,
    requisition_id TEXT,
    url TEXT,
    content_hash TEXT,
    location TEXT,
    location_type TEXT,
    workplace_type TEXT,
    city TEXT,
    state TEXT,
    country TEXT,
    region TEXT,
    department TEXT,
    functional_area TEXT,
    employment_type TEXT,
    seniority TEXT,
    language TEXT,
    salary_text TEXT,
    salary_min REAL,
    salary_max REAL,
    salary_currency TEXT,
    snippet TEXT,
    description TEXT,
    requirements TEXT,
    full_address TEXT,
    maps_url TEXT,
    posted_date TEXT,
    source_site_family TEXT,
    source_site_variant TEXT,
    source_confidence REAL DEFAULT 0.0,
    extraction_method TEXT,
    raw_source_ref TEXT,
    job_version INTEGER DEFAULT 1,
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
    evidence_json TEXT,
    taxonomy_version TEXT,
    detected_at TEXT
);

CREATE TABLE IF NOT EXISTS company_notes (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    note TEXT NOT NULL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS job_field_evidence (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    field_name TEXT NOT NULL,
    source_page_type TEXT,
    extraction_channel TEXT,
    raw_value TEXT,
    normalized_value TEXT,
    extraction_confidence REAL DEFAULT 0.0,
    parser_version TEXT,
    adapter_version TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS system_signal_evidence (
    id TEXT PRIMARY KEY,
    company_system_id TEXT NOT NULL REFERENCES company_systems(id),
    signal_type TEXT,
    matched_phrase TEXT,
    evidence_source TEXT,
    confidence_contribution REAL DEFAULT 0.0,
    exclusion_checks TEXT,
    taxonomy_version TEXT,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_active);
CREATE INDEX IF NOT EXISTS idx_jobs_hash ON jobs(content_hash);
CREATE INDEX IF NOT EXISTS idx_scrape_company ON scrape_history(company_id);
CREATE INDEX IF NOT EXISTS idx_systems_company ON company_systems(company_id);
CREATE INDEX IF NOT EXISTS idx_notes_company ON company_notes(company_id);
CREATE INDEX IF NOT EXISTS idx_job_field_evidence_job ON job_field_evidence(job_id);
CREATE INDEX IF NOT EXISTS idx_system_signal_evidence_system ON system_signal_evidence(company_system_id);
"""


async def _run_migrations(db: aiosqlite.Connection) -> None:
    await _ensure_columns(
        db,
        "companies",
        {
            "careers_source": "TEXT",
            "site_family": "TEXT",
            "site_variant": "TEXT",
        },
    )
    await _ensure_columns(
        db,
        "scrape_history",
        {
            "adapter_family": "TEXT",
            "adapter_variant": "TEXT",
            "artifact_refs": "TEXT",
        },
    )
    await _ensure_columns(
        db,
        "jobs",
        {
            "canonical_title": "TEXT",
            "requisition_id": "TEXT",
            "location_type": "TEXT",
            "workplace_type": "TEXT",
            "city": "TEXT",
            "state": "TEXT",
            "country": "TEXT",
            "region": "TEXT",
            "functional_area": "TEXT",
            "employment_type": "TEXT",
            "seniority": "TEXT",
            "language": "TEXT",
            "salary_text": "TEXT",
            "salary_min": "REAL",
            "salary_max": "REAL",
            "salary_currency": "TEXT",
            "source_site_family": "TEXT",
            "source_site_variant": "TEXT",
            "source_confidence": "REAL DEFAULT 0.0",
            "extraction_method": "TEXT",
            "raw_source_ref": "TEXT",
            "job_version": "INTEGER DEFAULT 1",
        },
    )
    await _ensure_columns(
        db,
        "company_systems",
        {
            "evidence_json": "TEXT",
            "taxonomy_version": "TEXT",
        },
    )
    await _ensure_columns(
        db,
        "jobs",
        {
            "enriched_at": "TEXT",
            "enrichment_attempts": "INTEGER DEFAULT 0",
            "enrichment_failed_at": "TEXT",
        },
    )

    # Intelligence tables
    await db.execute("""
        CREATE TABLE IF NOT EXISTS job_systems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            system_name TEXT NOT NULL,
            detected_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS job_intelligence_bullets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            category TEXT NOT NULL,
            bullet TEXT NOT NULL,
            confidence TEXT NOT NULL DEFAULT 'high',
            extracted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS company_intelligence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL UNIQUE,
            systems_json TEXT DEFAULT '[]',
            bullets_json TEXT DEFAULT '[]',
            hiring_velocity_json TEXT DEFAULT '{}',
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_job_systems_job_id ON job_systems(job_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_job_bullets_job_id ON job_intelligence_bullets(job_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_company_intelligence_name ON company_intelligence(company_name)")


async def _ensure_columns(db: aiosqlite.Connection, table: str, columns: dict[str, str]) -> None:
    async with db.execute(f"PRAGMA table_info({table})") as cur:
        existing = {row[1] for row in await cur.fetchall()}
    for column_name, column_type in columns.items():
        if column_name not in existing:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}")


def slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _job_content_hash(company_id: str, title: str, location: str | None) -> str:
    """Stable 32-hex-char (128-bit) hash used to deduplicate URL-less job
    listings (item 6).

    128 bits from SHA-256 provides negligible collision probability even at
    millions of jobs per company, while keeping the stored value compact.
    """
    raw = f"{company_id}|{title.lower().strip()}|{(location or '').lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ── Company CRUD ──────────────────────────────────────────────────────────────

async def create_company(
    name: str,
    careers_url: str | None = None,
    website_url: str | None = None,
    careers_source: str | None = None,
    site_family: str | None = None,
    site_variant: str | None = None,
    parent_company_name: str | None = None,
    region: str | None = None,
) -> dict:
    db = await get_db()
    now = _now()
    company_id = _uuid()
    slug = slugify(name)
    await db.execute(
        """INSERT INTO companies (
           id, name, slug, website_url, careers_url, careers_source, site_family, site_variant,
           parent_company_name, region, first_seen, last_seen, created_at
        ) VALUES (
           :id, :name, :slug, :website_url, :careers_url, :careers_source, :site_family, :site_variant,
           :parent_company_name, :region, :first_seen, :last_seen, :created_at
        )""",
        {
            "id": company_id,
            "name": name,
            "slug": slug,
            "website_url": website_url,
            "careers_url": careers_url,
            "careers_source": careers_source,
            "site_family": site_family,
            "site_variant": site_variant,
            "parent_company_name": parent_company_name,
            "region": region,
            "first_seen": now,
            "last_seen": now,
            "created_at": now,
        },
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
    allowed = {
        "name", "slug", "website_url", "careers_url", "careers_source", "site_family",
        "site_variant", "parent_company_name", "region", "notes_text",
    }
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
    adapter_family: str | None,
    adapter_variant: str | None,
    jobs_found: int,
    elapsed_ms: int,
    error: str | None,
    html_size: int | None,
    artifact_refs: dict | None,
    deep: bool,
) -> str:
    db = await get_db()
    scrape_id = _uuid()
    await db.execute(
        "INSERT INTO scrape_history (id, company_id, url, parser_used, adapter_family, adapter_variant, jobs_found, elapsed_ms, error, html_size, artifact_refs, deep, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            scrape_id,
            company_id,
            url,
            parser_used,
            adapter_family,
            adapter_variant,
            jobs_found,
            elapsed_ms,
            error,
            html_size,
            json.dumps(artifact_refs or {}),
            int(deep),
            _now(),
        ),
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
        rows = [dict(r) for r in await cur.fetchall()]
    for row in rows:
        if row.get("artifact_refs"):
            try:
                row["artifact_refs"] = json.loads(row["artifact_refs"])
            except (json.JSONDecodeError, TypeError):
                pass
    return rows


# ── Jobs ──────────────────────────────────────────────────────────────────────

_JOB_INSERT_FIELDS = (
    "id", "company_id", "scrape_id", "title", "canonical_title", "requisition_id", "url", "content_hash",
    "location", "location_type", "workplace_type", "city", "state", "country", "region", "department",
    "functional_area", "employment_type", "seniority", "language", "salary_text", "salary_min", "salary_max",
    "salary_currency", "snippet", "description", "requirements", "full_address", "maps_url", "posted_date",
    "source_site_family", "source_site_variant", "source_confidence", "extraction_method", "raw_source_ref",
    "first_seen", "last_seen", "job_version",
)

_JOB_UPDATE_FIELDS = (
    "title", "location", "department", "snippet", "canonical_title", "requisition_id", "employment_type",
    "workplace_type", "location_type", "city", "state", "country", "region", "functional_area", "language",
    "seniority", "salary_text", "salary_min", "salary_max", "salary_currency", "description", "requirements",
    "full_address", "maps_url", "posted_date", "source_site_family", "source_site_variant", "source_confidence",
    "extraction_method", "raw_source_ref",
)

_JOB_PRESERVE_IF_NONE = {
    "canonical_title", "requisition_id", "employment_type", "workplace_type", "location_type", "city", "state",
    "country", "region", "functional_area", "language", "seniority", "salary_text", "salary_min", "salary_max",
    "salary_currency", "description", "requirements", "full_address", "maps_url", "posted_date",
    "source_site_family", "source_site_variant", "source_confidence", "extraction_method", "raw_source_ref",
}


def _build_job_payload(job: dict, *, company_id: str, scrape_id: str, now: str, content_hash: str) -> dict:
    requirements = job.get("requirements")
    requirements_value = json.dumps(requirements) if isinstance(requirements, list) else requirements
    return {
        "company_id": company_id,
        "scrape_id": scrape_id,
        "title": job.get("title", ""),
        "canonical_title": job.get("canonical_title"),
        "requisition_id": job.get("requisition_id"),
        "url": job.get("url"),
        "content_hash": content_hash,
        "location": job.get("location"),
        "location_type": job.get("location_type"),
        "workplace_type": job.get("workplace_type"),
        "city": job.get("city"),
        "state": job.get("state"),
        "country": job.get("country"),
        "region": job.get("region"),
        "department": job.get("department"),
        "functional_area": job.get("functional_area"),
        "employment_type": job.get("employment_type"),
        "seniority": job.get("seniority"),
        "language": job.get("language"),
        "salary_text": job.get("salary_text"),
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "salary_currency": job.get("salary_currency"),
        "snippet": job.get("snippet"),
        "description": job.get("description"),
        "requirements": requirements_value,
        "full_address": job.get("full_address"),
        "maps_url": job.get("maps_url"),
        "posted_date": job.get("posted_date"),
        "source_site_family": job.get("source_site_family"),
        "source_site_variant": job.get("source_site_variant"),
        "source_confidence": job.get("source_confidence"),
        "extraction_method": job.get("extraction_method"),
        "raw_source_ref": job.get("raw_source_ref"),
        "first_seen": now,
        "last_seen": now,
        "job_version": 1,
    }


def _job_update_sql() -> str:
    assignments = ["scrape_id = :scrape_id"]
    for field_name in _JOB_UPDATE_FIELDS:
        if field_name in _JOB_PRESERVE_IF_NONE:
            assignments.append(f"{field_name} = COALESCE(:{field_name}, {field_name})")
        else:
            assignments.append(f"{field_name} = :{field_name}")
    assignments.extend(
        [
            "last_seen = :last_seen",
            "is_active = 1",
            "content_hash = :content_hash",
            "job_version = :job_version",
        ]
    )
    return f"UPDATE jobs SET {', '.join(assignments)} WHERE id = :id"


def _job_insert_sql() -> str:
    columns = ", ".join(_JOB_INSERT_FIELDS) + ", is_active"
    placeholders = ", ".join(f":{field_name}" for field_name in _JOB_INSERT_FIELDS) + ", 1"
    return f"INSERT INTO jobs ({columns}) VALUES ({placeholders})"


_JOB_UPDATE_SQL = _job_update_sql()
_JOB_INSERT_SQL = _job_insert_sql()


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
        field_evidence = j.get("_field_evidence", [])
        job_payload = _build_job_payload(j, company_id=company_id, scrape_id=scrape_id, now=now, content_hash=content_hash)

        seen_urls.add(job_url)
        seen_hashes.add(content_hash)

        existing = None
        if job_url and job_url in existing_by_url:
            existing = existing_by_url[job_url]
        elif content_hash in existing_by_hash:
            existing = existing_by_hash[content_hash]

        if existing:
            existing_version = existing.get("job_version")
            next_version = int(existing_version) + 1 if existing_version is not None else 1
            await db.execute(_JOB_UPDATE_SQL, {**job_payload, "job_version": next_version, "id": existing["id"]})
            job_id = existing["id"]
        else:
            job_id = _uuid()
            await db.execute(_JOB_INSERT_SQL, {**job_payload, "id": job_id})
        await db.execute("DELETE FROM job_field_evidence WHERE job_id = ?", (job_id,))
        for evidence in field_evidence:
            await db.execute(
                """INSERT INTO job_field_evidence (
                   id, job_id, field_name, source_page_type, extraction_channel, raw_value, normalized_value,
                   extraction_confidence, parser_version, adapter_version, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    _uuid(),
                    job_id,
                    evidence.get("field_name"),
                    evidence.get("source_page_type"),
                    evidence.get("extraction_channel"),
                    evidence.get("raw_value"),
                    evidence.get("normalized_value"),
                    evidence.get("extraction_confidence", 0.0),
                    evidence.get("parser_version"),
                    evidence.get("adapter_version"),
                    now,
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
    if not row:
        return None
    job = dict(row)
    if job.get("requirements"):
        try:
            job["requirements"] = json.loads(job["requirements"])
        except (json.JSONDecodeError, TypeError):
            pass
    async with db.execute(
        "SELECT field_name, source_page_type, extraction_channel, raw_value, normalized_value, extraction_confidence, parser_version, adapter_version FROM job_field_evidence WHERE job_id = ? ORDER BY created_at, field_name",
        (job_id,),
    ) as cur:
        job["field_evidence"] = [dict(r) for r in await cur.fetchall()]
    return job


# ── Company Systems ───────────────────────────────────────────────────────────

async def save_systems(company_id: str, systems: list[dict]) -> None:
    db = await get_db()
    now = _now()
    async with db.execute("SELECT id FROM company_systems WHERE company_id = ?", (company_id,)) as cur:
        existing = [row[0] for row in await cur.fetchall()]
    for system_id in existing:
        await db.execute("DELETE FROM system_signal_evidence WHERE company_system_id = ?", (system_id,))
    await db.execute("DELETE FROM company_systems WHERE company_id = ?", (company_id,))
    for s in systems:
        company_system_id = _uuid()
        await db.execute(
            "INSERT INTO company_systems (id, company_id, system_name, system_id, category, confidence, matched_keywords, source, evidence_json, taxonomy_version, detected_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                company_system_id,
                company_id,
                s["system_name"],
                s["system_id"],
                s["category"],
                s["confidence"],
                json.dumps(s.get("matched_keywords", [])),
                s.get("source", "careers_page"),
                json.dumps(s.get("evidence", [])),
                s.get("taxonomy_version"),
                now,
            ),
        )
        for evidence in s.get("evidence", []):
            await db.execute(
                """INSERT INTO system_signal_evidence (
                   id, company_system_id, signal_type, matched_phrase, evidence_source,
                   confidence_contribution, exclusion_checks, taxonomy_version, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    _uuid(),
                    company_system_id,
                    evidence.get("signal_type"),
                    evidence.get("matched_phrase"),
                    evidence.get("evidence_source"),
                    evidence.get("confidence_contribution", 0.0),
                    json.dumps(evidence.get("exclusion_checks", [])),
                    s.get("taxonomy_version"),
                    now,
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
        if d.get("evidence_json"):
            try:
                d["evidence"] = json.loads(d["evidence_json"])
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


# ── Intelligence ──────────────────────────────────────────────────────────────

async def save_job_systems(job_id: str, systems: list[str]) -> None:
    db = await get_db()
    await db.execute("DELETE FROM job_systems WHERE job_id = ?", (job_id,))
    for name in systems:
        await db.execute(
            "INSERT INTO job_systems (job_id, system_name) VALUES (?, ?)",
            (job_id, name),
        )
    await db.commit()


async def save_job_bullets(job_id: str, bullets: list[dict]) -> None:
    db = await get_db()
    await db.execute("DELETE FROM job_intelligence_bullets WHERE job_id = ?", (job_id,))
    for b in bullets:
        await db.execute(
            "INSERT INTO job_intelligence_bullets (job_id, category, bullet, confidence) VALUES (?, ?, ?, ?)",
            (job_id, b.get("category", ""), b.get("bullet", ""), b.get("confidence", "high")),
        )
    await db.commit()


async def get_company_intelligence(company_name: str) -> dict | None:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM company_intelligence WHERE company_name = ?", (company_name,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    d = dict(row)
    for field in ("systems_json", "bullets_json", "hiring_velocity_json"):
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


async def upsert_company_intelligence(
    company_name: str,
    systems_json: str,
    bullets_json: str,
    hiring_velocity_json: str,
) -> None:
    db = await get_db()
    await db.execute(
        """INSERT INTO company_intelligence (company_name, systems_json, bullets_json, hiring_velocity_json, last_updated)
           VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(company_name) DO UPDATE SET
               systems_json = excluded.systems_json,
               bullets_json = excluded.bullets_json,
               hiring_velocity_json = excluded.hiring_velocity_json,
               last_updated = CURRENT_TIMESTAMP""",
        (company_name, systems_json, bullets_json, hiring_velocity_json),
    )
    await db.commit()


async def list_company_intelligence(page: int = 1, limit: int = 50) -> dict:
    db = await get_db()
    offset = (page - 1) * limit
    async with db.execute(
        "SELECT * FROM company_intelligence ORDER BY last_updated DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]
    async with db.execute("SELECT COUNT(*) FROM company_intelligence") as cur:
        total = (await cur.fetchone())[0]
    for row in rows:
        for field in ("systems_json", "bullets_json", "hiring_velocity_json"):
            if row.get(field):
                try:
                    row[field] = json.loads(row[field])
                except (json.JSONDecodeError, TypeError):
                    pass
    return {"companies": rows, "total": total, "page": page, "limit": limit}


async def get_stats() -> dict:
    from app.site_adapters import adapter_count
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
        "parsers_available": adapter_count(include_generic=True),
    }


# ── Enrichment queue ──────────────────────────────────────────────────────────

async def get_enrichment_queue(limit: int = 20) -> list[dict]:
    """Jobs not yet enriched, with text content, capped at 3 attempts."""
    db = await get_db()
    sql = """
        SELECT j.id, j.title, c.name as company_name,
               COALESCE(j.description, j.snippet) as text_content
        FROM jobs j
        LEFT JOIN companies c ON j.company_id = c.id
        WHERE (j.snippet IS NOT NULL OR j.description IS NOT NULL)
          AND j.enriched_at IS NULL
          AND (j.enrichment_attempts IS NULL OR j.enrichment_attempts < 3)
        LIMIT ?
    """
    async with db.execute(sql, (limit,)) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def mark_job_enriched(job_id: str) -> None:
    db = await get_db()
    await db.execute(
        """UPDATE jobs SET enriched_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (job_id,),
    )
    await db.commit()


async def mark_job_enrichment_failed(job_id: str) -> None:
    db = await get_db()
    await db.execute(
        """UPDATE jobs SET enrichment_failed_at = CURRENT_TIMESTAMP,
                          enrichment_attempts = COALESCE(enrichment_attempts, 0) + 1
           WHERE id = ?""",
        (job_id,),
    )
    await db.commit()
