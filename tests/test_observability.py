"""Tests for Phase 6 observability endpoints (db layer).

Uses an in-memory SQLite database initialised via db.init_db() so the
queries run against a real schema without touching the filesystem.
"""
import pytest

from app import db


@pytest.fixture(autouse=True)
async def fresh_db():
    """Use an in-memory DB for each test, regardless of SCRAPER_DB_PATH."""
    original_path = db.DB_PATH
    db.DB_PATH = ":memory:"
    if db._conn:
        await db._conn.close()
        db._conn = None
    await db.init_db()
    yield
    if db._conn:
        await db._conn.close()
        db._conn = None
    db.DB_PATH = original_path


async def _insert_scrape(
    *,
    adapter_family: str = "greenhouse",
    adapter_variant: str = "playwright",
    jobs_found: int = 5,
    elapsed_ms: int = 1000,
    error: str | None = None,
    error_code: str | None = None,
    days_ago: int = 0,
) -> None:
    conn = await db.get_db()
    created = f"datetime('now', '-{days_ago} days')"
    await conn.execute(
        f"""INSERT INTO scrape_history
            (id, company_id, url, parser_used, adapter_family, adapter_variant,
             jobs_found, elapsed_ms, error, error_code, artifact_refs, deep, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,{created})""",
        (
            db._uuid(), None, "https://example.com/careers", "generic",
            adapter_family, adapter_variant,
            jobs_found, elapsed_ms, error, error_code, "{}", 0,
        ),
    )
    await conn.commit()


# ── get_scrape_health ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_unhealthy_when_no_scrapes():
    result = await db.get_scrape_health()
    assert result["status"] == "unhealthy"
    assert result["scrapes_24h"] == 0


@pytest.mark.asyncio
async def test_health_healthy_all_success():
    for _ in range(5):
        await _insert_scrape()
    result = await db.get_scrape_health()
    assert result["status"] == "healthy"
    assert result["success_rate_24h"] == 1.0
    assert result["error_rate_24h"] == 0.0
    assert result["scrapes_24h"] == 5


@pytest.mark.asyncio
async def test_health_degraded_at_80_percent():
    for _ in range(8):
        await _insert_scrape()
    for _ in range(2):
        await _insert_scrape(error="blocked", error_code="ip_blocked")
    result = await db.get_scrape_health()
    assert result["status"] == "degraded"
    assert result["success_rate_24h"] == 0.8


@pytest.mark.asyncio
async def test_health_unhealthy_below_70_percent():
    for _ in range(3):
        await _insert_scrape()
    for _ in range(7):
        await _insert_scrape(error="fail", error_code="parse_failure")
    result = await db.get_scrape_health()
    assert result["status"] == "unhealthy"
    assert result["success_rate_24h"] == 0.3


@pytest.mark.asyncio
async def test_health_excludes_scrapes_older_than_24h():
    await _insert_scrape(days_ago=2)  # outside window — should not count
    result = await db.get_scrape_health()
    assert result["scrapes_24h"] == 0
    assert result["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_health_avg_jobs():
    await _insert_scrape(jobs_found=10)
    await _insert_scrape(jobs_found=20)
    result = await db.get_scrape_health()
    assert result["avg_jobs_24h"] == 15.0


# ── get_adapter_stats ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_adapter_stats_empty():
    result = await db.get_adapter_stats()
    assert result == {"adapters": []}


@pytest.mark.asyncio
async def test_adapter_stats_groups_by_family_and_variant():
    await _insert_scrape(adapter_family="greenhouse", adapter_variant="api")
    await _insert_scrape(adapter_family="greenhouse", adapter_variant="api")
    await _insert_scrape(adapter_family="greenhouse", adapter_variant="playwright")
    result = await db.get_adapter_stats()
    assert len(result["adapters"]) == 2
    top = result["adapters"][0]
    assert top["adapter_family"] == "greenhouse"
    assert top["adapter_variant"] == "api"
    assert top["total"] == 2


@pytest.mark.asyncio
async def test_adapter_stats_success_rate():
    await _insert_scrape(adapter_family="lever", adapter_variant="playwright")
    await _insert_scrape(adapter_family="lever", adapter_variant="playwright",
                         error="fail", error_code="parse_failure")
    result = await db.get_adapter_stats()
    row = result["adapters"][0]
    assert row["success_rate"] == 0.5
    assert "successes" not in row


@pytest.mark.asyncio
async def test_adapter_stats_sorted_by_total_desc():
    await _insert_scrape(adapter_family="greenhouse", adapter_variant="api")
    for _ in range(3):
        await _insert_scrape(adapter_family="lever", adapter_variant="playwright")
    result = await db.get_adapter_stats()
    assert result["adapters"][0]["adapter_family"] == "lever"


# ── get_failure_trends ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_failure_trends_empty_when_no_errors():
    await _insert_scrape()  # success — should not appear
    result = await db.get_failure_trends()
    assert result["days"] == 7
    assert result["trends"] == []


@pytest.mark.asyncio
async def test_failure_trends_counts_error_codes():
    await _insert_scrape(error="blocked", error_code="ip_blocked")
    await _insert_scrape(error="blocked", error_code="ip_blocked")
    await _insert_scrape(error="fail", error_code="parse_failure")
    result = await db.get_failure_trends()
    by_code = {r["error_code"]: r["count"] for r in result["trends"]}
    assert by_code["ip_blocked"] == 2
    assert by_code["parse_failure"] == 1


@pytest.mark.asyncio
async def test_failure_trends_excludes_old_errors():
    await _insert_scrape(error="old", error_code="ip_blocked", days_ago=10)
    result = await db.get_failure_trends(days=7)
    assert result["trends"] == []


@pytest.mark.asyncio
async def test_failure_trends_respects_days_param():
    await _insert_scrape(error="recent", error_code="captcha_detected", days_ago=2)
    await _insert_scrape(error="old", error_code="ip_blocked", days_ago=10)
    result = await db.get_failure_trends(days=7)
    assert len(result["trends"]) == 1
    assert result["trends"][0]["error_code"] == "captcha_detected"
