"""Intelligence API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db import get_company_intelligence, get_db, get_job, list_company_intelligence
from app.intelligence.enricher import enrich_job

router = APIRouter(prefix="/intelligence")


@router.get("/companies")
async def companies_list(page: int = 1, limit: int = 50):
    return await list_company_intelligence(page=page, limit=limit)


@router.get("/companies/{company_name}")
async def company_detail(company_name: str):
    result = await get_company_intelligence(company_name)
    if not result:
        raise HTTPException(status_code=404, detail="Company intelligence not found")
    return result


@router.get("/digest/daily")
async def daily_digest():
    db = await get_db()

    async with db.execute(
        """SELECT c.name, COUNT(j.id) as new_jobs
           FROM jobs j
           JOIN companies c ON j.company_id = c.id
           LEFT JOIN company_intelligence ci ON c.name = ci.company_name
           WHERE j.first_seen > datetime('now', '-1 day')
             AND ci.company_name IS NULL
           GROUP BY c.name
           ORDER BY new_jobs DESC
           LIMIT 20"""
    ) as cur:
        new_companies = [dict(r) for r in await cur.fetchall()]

    async with db.execute(
        """SELECT c.name, COUNT(j.id) as new_jobs, ci.systems_json, ci.bullets_json
           FROM jobs j
           JOIN companies c ON j.company_id = c.id
           LEFT JOIN company_intelligence ci ON c.name = ci.company_name
           WHERE j.first_seen > datetime('now', '-1 day')
             AND ci.company_name IS NOT NULL
           GROUP BY c.name
           ORDER BY new_jobs DESC
           LIMIT 20"""
    ) as cur:
        new_roles = [dict(r) for r in await cur.fetchall()]

    async with db.execute(
        """SELECT c.name,
               SUM(CASE WHEN j.first_seen > datetime('now', '-7 day') THEN 1 ELSE 0 END) as recent_7d,
               SUM(CASE WHEN j.first_seen BETWEEN datetime('now', '-14 day') AND datetime('now', '-7 day') THEN 1 ELSE 0 END) as prior_7d
           FROM jobs j
           JOIN companies c ON j.company_id = c.id
           GROUP BY c.name
           HAVING prior_7d > 0 AND recent_7d >= prior_7d * 2
           ORDER BY recent_7d DESC
           LIMIT 10"""
    ) as cur:
        surging = [dict(r) for r in await cur.fetchall()]

    return {
        "new_companies_24h": new_companies,
        "new_roles_24h": new_roles,
        "hiring_surge": surging,
    }


@router.post("/enrich/{job_id}")
async def enrich_single(job_id: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    snippet = job.get("snippet") or job.get("description") or ""
    if not snippet:
        raise HTTPException(status_code=422, detail="Job has no snippet or description to enrich")

    from app.db import get_db as _get_db
    db = await _get_db()
    async with db.execute(
        "SELECT js.system_name FROM job_systems js WHERE js.job_id = ?", (job_id,)
    ) as cur:
        existing_systems = [row[0] for row in await cur.fetchall()]

    await enrich_job(
        job_id=job_id,
        title=job.get("title", ""),
        company_name=job.get("company_name", ""),
        snippet=snippet,
    )

    async with db.execute(
        "SELECT js.system_name FROM job_systems js WHERE js.job_id = ?", (job_id,)
    ) as cur:
        systems = [row[0] for row in await cur.fetchall()]

    async with db.execute(
        "SELECT COUNT(*) FROM job_intelligence_bullets WHERE job_id = ?", (job_id,)
    ) as cur:
        bullets_count = (await cur.fetchone())[0]

    return {"enriched": True, "systems": systems, "bullets_count": bullets_count}
