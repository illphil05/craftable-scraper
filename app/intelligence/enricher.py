"""Background enrichment worker: detect systems and extract bullets per job."""
from __future__ import annotations

import json

from app.db import (
    get_db,
    get_enrichment_queue,
    mark_job_enriched,
    mark_job_enrichment_failed,
    save_job_bullets,
    save_job_systems,
    upsert_company_intelligence,
)
from app.intelligence.extractor import detect_systems, extract_bullets
from app.logging_config import get_logger

log = get_logger("enricher")


async def _aggregate_company_intelligence(company_name: str) -> None:
    db = await get_db()

    async with db.execute(
        """SELECT js.system_name, COUNT(*) as count, MAX(js.detected_at) as last_seen
           FROM job_systems js
           JOIN jobs j ON js.job_id = j.id
           JOIN companies c ON j.company_id = c.id
           WHERE c.name = ?
           GROUP BY js.system_name
           ORDER BY count DESC""",
        (company_name,),
    ) as cur:
        systems = [dict(r) for r in await cur.fetchall()]

    async with db.execute(
        """SELECT jib.category, jib.bullet, jib.job_id, jib.extracted_at
           FROM job_intelligence_bullets jib
           JOIN jobs j ON jib.job_id = j.id
           JOIN companies c ON j.company_id = c.id
           WHERE c.name = ?
           ORDER BY jib.extracted_at DESC""",
        (company_name,),
    ) as cur:
        bullets = [dict(r) for r in await cur.fetchall()]

    await upsert_company_intelligence(
        company_name=company_name,
        systems_json=json.dumps(systems),
        bullets_json=json.dumps(bullets),
        hiring_velocity_json="{}",
    )


async def enrich_job(job_id: str, title: str, company_name: str, text_content: str) -> None:
    systems = detect_systems(text_content)
    await save_job_systems(job_id, systems)

    all_bullets = await extract_bullets(text_content)
    high_bullets = [b for b in all_bullets if b.get("confidence") == "high"]
    await save_job_bullets(job_id, high_bullets)

    await mark_job_enriched(job_id)
    if company_name:
        try:
            await _aggregate_company_intelligence(company_name)
        except Exception as exc:
            log.error("Aggregation failed for company %s: %s", company_name, exc)
    log.info(
        "Enriched job %s (%s): %d systems, %d bullets",
        job_id, title, len(systems), len(high_bullets),
    )


async def run_enrichment_batch() -> int:
    queue = await get_enrichment_queue(limit=10)
    if not queue:
        return 0
    count = 0
    for job in queue:
        try:
            await enrich_job(
                job_id=job["id"],
                title=job.get("title", ""),
                company_name=job.get("company_name", ""),
                text_content=job["text_content"],
            )
            count += 1
        except Exception as exc:
            log.error("Enrichment failed for job %s: %s", job["id"], exc)
            try:
                await mark_job_enrichment_failed(job["id"])
            except Exception as mark_exc:
                log.error("Failed to record enrichment failure for job %s: %s", job["id"], mark_exc)
    return count
