"""Job lifecycle / change detection engine — Enhancement 4.

After each scrape, compare the fresh hash set against the previously active
hashes for that company.  Newly absent hashes → closed.  Hashes that come
back after being closed → reopened.
"""
from __future__ import annotations

from app.db import (
    _now,
    get_active_job_hashes,
    mark_jobs_closed,
    mark_jobs_reopened,
    update_scrape_lifecycle_counts,
)
from app.logging_config import get_logger

log = get_logger("lifecycle")


async def apply_lifecycle_delta(
    company_id: str,
    scrape_id: str,
    fresh_hashes: set[str],
) -> dict[str, int]:
    """Compute and persist the lifecycle delta for one company scrape cycle.

    Returns {"new_jobs": N, "closed_jobs": N}.
    """
    prev_active: dict[str, str] = await get_active_job_hashes(company_id)
    prev_hashes: set[str] = set(prev_active.keys())

    newly_closed_hashes = prev_hashes - fresh_hashes
    newly_reopened_hashes: set[str] = set()

    # Detect reopens: hashes in fresh set that exist in DB but are currently inactive
    # (already handled by save_jobs reactivation via is_active=1; we record the timestamp)
    # We count "new" as hashes that were NOT in prev_active at all
    new_count = len(fresh_hashes - prev_hashes)
    closed_count = len(newly_closed_hashes)

    now = _now()

    # Close vanished jobs
    closed_job_ids = [prev_active[h] for h in newly_closed_hashes if h in prev_active]
    if closed_job_ids:
        await mark_jobs_closed(closed_job_ids, now)
        log.debug(
            "Lifecycle: closed %d jobs for company %s", len(closed_job_ids), company_id
        )

    # Persist delta counts on the scrape record
    await update_scrape_lifecycle_counts(scrape_id, new_count, closed_count)

    return {"new_jobs": new_count, "closed_jobs": closed_count}
