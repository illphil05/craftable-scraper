"""Intelligence API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.db import get_company_intelligence, get_db, get_job, list_company_intelligence
from app.intelligence.enricher import enrich_job

router = APIRouter(prefix="/intelligence")


@router.get("/companies")
async def companies_list(page: int = 1, limit: int = Query(default=50, ge=1, le=500)):
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
        """SELECT c.name, COUNT(j.id) as new_jobs
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
async def enrich_single(job_id: str, force: bool = False):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not force and job.get("enriched_at"):
        return {
            "enriched": False,
            "skipped": True,
            "reason": "already enriched",
            "enriched_at": job["enriched_at"],
        }

    text_content = job.get("description") or job.get("snippet") or ""
    if not text_content:
        raise HTTPException(status_code=422, detail="Job has no text content to enrich")

    await enrich_job(
        job_id=job_id,
        title=job.get("title", ""),
        company_name=job.get("company_name", ""),
        text_content=text_content,
    )

    db = await get_db()
    async with db.execute(
        "SELECT system_name FROM job_systems WHERE job_id = ?", (job_id,)
    ) as cur:
        systems = [row[0] for row in await cur.fetchall()]
    async with db.execute(
        "SELECT COUNT(*) FROM job_intelligence_bullets WHERE job_id = ?", (job_id,)
    ) as cur:
        bullets_count = (await cur.fetchone())[0]

    return {"enriched": True, "systems": systems, "bullets_count": bullets_count}
