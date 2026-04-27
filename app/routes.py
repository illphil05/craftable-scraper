"""API route handlers for the dashboard.

All handlers are async to work with the aiosqlite-backed db module.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import db
from app.tech_detect import detect_systems

router = APIRouter(prefix="/api")


# ── Request/Response models ───────────────────────────────────────────────────

class CompanyCreate(BaseModel):
    name: str
    website_url: str | None = None
    careers_url: str | None = None
    careers_source: str | None = None
    site_family: str | None = None
    site_variant: str | None = None
    parent_company_name: str | None = None
    region: str | None = None


class CompanyUpdate(BaseModel):
    name: str | None = None
    website_url: str | None = None
    careers_url: str | None = None
    careers_source: str | None = None
    site_family: str | None = None
    site_variant: str | None = None
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
    adapter_family: str | None = None
    adapter_variant: str | None = None
    jobs_found: int
    elapsed_ms: int
    error: str | None = None
    html_size: int | None = None
    artifact_refs: dict[str, Any] = Field(default_factory=dict)
    deep: bool = False
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    html: str = ""


# ── Company routes ────────────────────────────────────────────────────────────

@router.get("/companies")
async def list_companies(search: str = "", region: str = "", page: int = 1, limit: int = 50):
    return await db.list_companies(search=search, region=region, page=page, limit=limit)


@router.get("/companies/{company_id}")
async def get_company(company_id: str):
    c = await db.get_company(company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    c["systems"] = await db.get_systems(company_id)
    c["notes"] = await db.get_notes(company_id)
    return c


@router.post("/companies")
async def create_company(body: CompanyCreate):
    return await db.create_company(
        name=body.name,
        website_url=body.website_url,
        careers_url=body.careers_url,
        careers_source=body.careers_source,
        site_family=body.site_family,
        site_variant=body.site_variant,
        parent_company_name=body.parent_company_name,
        region=body.region,
    )


@router.put("/companies/{company_id}")
async def update_company(company_id: str, body: CompanyUpdate):
    c = await db.update_company(company_id, **body.model_dump(exclude_none=True))
    if not c:
        raise HTTPException(404, "Company not found")
    return c


@router.delete("/companies/{company_id}")
async def delete_company(company_id: str):
    await db.delete_company(company_id)
    return {"ok": True}


# ── Company sub-resources ─────────────────────────────────────────────────────

@router.get("/companies/{company_id}/jobs")
async def company_jobs(company_id: str, is_active: bool | None = None, page: int = 1, limit: int = 50):
    return await db.list_jobs(company_id=company_id, is_active=is_active, page=page, limit=limit)


@router.get("/companies/{company_id}/scrapes")
async def company_scrapes(company_id: str):
    return await db.get_scrape_history(company_id)


@router.get("/companies/{company_id}/systems")
async def company_systems(company_id: str):
    return await db.get_systems(company_id)


@router.post("/companies/{company_id}/notes")
async def add_note(company_id: str, body: NoteCreate):
    return await db.add_note(company_id, body.note)


@router.delete("/companies/{company_id}/notes/{note_id}")
async def delete_note(company_id: str, note_id: str):
    await db.delete_note(note_id)
    return {"ok": True}


# ── Jobs ──────────────────────────────────────────────────────────────────────

@router.get("/jobs")
async def list_jobs(
    search: str = "",
    company_id: str = "",
    department: str = "",
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 50,
):
    return await db.list_jobs(
        company_id=company_id or None,
        search=search,
        department=department,
        is_active=is_active,
        page=page,
        limit=limit,
    )


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    j = await db.get_job(job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return j


# ── Dashboard data ────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats():
    return await db.get_stats()


@router.get("/systems-heatmap")
async def systems_heatmap():
    return await db.get_systems_heatmap()


@router.get("/recent-scrapes")
async def recent_scrapes(limit: int = 20):
    return await db.get_recent_scrapes(limit=limit)


# ── Save scrape results to DB ─────────────────────────────────────────────────

@router.post("/save-scrape")
async def save_scrape(body: SaveScrapeRequest):
    """Save scrape results to the database. Called after a successful /scrape."""
    company_id = body.company_id

    # Auto-find or create company
    if not company_id and body.careers_url:
        existing = await db.find_company_by_careers_url(body.careers_url)
        if existing:
            company_id = existing["id"]
        elif body.company_name:
            c = await db.create_company(
                name=body.company_name,
                careers_url=body.careers_url,
                careers_source="career_site",
                site_family=body.adapter_family,
                site_variant=body.adapter_variant,
            )
            company_id = c["id"]

    if not company_id:
        raise HTTPException(400, "No company_id and could not auto-resolve company")

    scrape_id = await db.save_scrape(
        company_id=company_id,
        url=body.careers_url,
        parser_used=body.parser_used,
        adapter_family=body.adapter_family,
        adapter_variant=body.adapter_variant,
        jobs_found=body.jobs_found,
        elapsed_ms=body.elapsed_ms,
        error=body.error,
        html_size=body.html_size,
        artifact_refs=body.artifact_refs,
        deep=body.deep,
    )

    if body.jobs:
        await db.save_jobs(company_id, scrape_id, body.jobs)

    if body.html:
        systems = detect_systems(body.html, body.jobs)
        if systems:
            await db.save_systems(company_id, systems)

    company = await db.get_company(company_id)
    return {"ok": True, "company_id": company_id, "scrape_id": scrape_id, "company": company}
