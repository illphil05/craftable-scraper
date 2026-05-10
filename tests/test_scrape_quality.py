"""Tests for Phase 3 scrape quality scoring (_compute_scrape_quality)."""
import pytest
from unittest.mock import MagicMock

from app.scraper import _compute_scrape_quality


def _adapter(confidence: float = 0.95) -> MagicMock:
    adapter = MagicMock()
    adapter.match_confidence.return_value = confidence
    return adapter


def _result(
    *,
    jobs=None,
    method="playwright:greenhouse",
    error_code=None,
    attempts=None,
    url="https://boards.greenhouse.io/acme",
) -> dict:
    jobs = jobs or []
    return {
        "jobs": jobs,
        "jobs_count": len(jobs),
        "method": method,
        "error_code": error_code,
        "extraction_attempts": attempts or [{"method": method}],
        "url": url,
    }


# ── Score and grade ───────────────────────────────────────────────────────────

def test_high_confidence_no_error_is_high_grade():
    q = _compute_scrape_quality(_result(), _adapter(0.95))
    assert q["grade"] == "high"
    assert q["score"] >= 0.75


def test_api_first_zero_fallback_depth():
    q = _compute_scrape_quality(
        _result(method="api:greenhouse", attempts=[{"method": "api:greenhouse"}]),
        _adapter(0.95),
    )
    assert q["signals"]["fallback_depth"] == 0
    assert q["signals"]["used_fallback"] is False


def test_playwright_single_attempt_is_depth_1():
    q = _compute_scrape_quality(_result(), _adapter(0.95))
    assert q["signals"]["fallback_depth"] == 1
    assert q["signals"]["used_fallback"] is False


def test_playwright_retry_is_depth_2():
    q = _compute_scrape_quality(
        _result(attempts=[
            {"method": "playwright:greenhouse", "attempt": 1},
            {"method": "playwright:greenhouse", "attempt": 2},
        ]),
        _adapter(0.95),
    )
    assert q["signals"]["fallback_depth"] == 2
    assert q["signals"]["used_fallback"] is True


def test_brightdata_is_depth_2():
    q = _compute_scrape_quality(
        _result(
            method="brightdata:unlocker:greenhouse",
            attempts=[{"method": "playwright:greenhouse"}, {"method": "brightdata:unlocker"}],
        ),
        _adapter(0.95),
    )
    assert q["signals"]["fallback_depth"] == 2
    assert q["signals"]["used_fallback"] is True


def test_botasaurus_is_depth_3():
    q = _compute_scrape_quality(
        _result(
            method="botasaurus:greenhouse",
            attempts=[{"method": "playwright:greenhouse"}, {"method": "botasaurus:greenhouse"}],
        ),
        _adapter(0.95),
    )
    assert q["signals"]["fallback_depth"] == 3
    assert q["signals"]["used_fallback"] is True


# ── Error code penalties ──────────────────────────────────────────────────────

def test_parse_failure_reduces_score():
    no_err = _compute_scrape_quality(_result(error_code=None), _adapter(0.95))
    with_err = _compute_scrape_quality(_result(error_code="parse_failure"), _adapter(0.95))
    assert with_err["score"] < no_err["score"]


def test_ip_blocked_large_penalty():
    q = _compute_scrape_quality(_result(error_code="ip_blocked"), _adapter(0.95))
    assert q["score"] <= 0.50


def test_captcha_grade_medium_or_low():
    q = _compute_scrape_quality(_result(error_code="captcha_detected"), _adapter(0.95))
    assert q["grade"] in ("medium", "low")


# ── "0 jobs = no openings" vs "0 jobs = parse failed" ────────────────────────

def test_zero_jobs_no_error_stays_high():
    """Empty board with no error — scrape worked, company just has no openings."""
    q = _compute_scrape_quality(_result(jobs=[], error_code=None), _adapter(0.95))
    assert q["grade"] == "high"
    assert q["signals"]["error_code"] is None


def test_zero_jobs_parse_failure_downgrades():
    """Parse failed — consumer should not trust the zero-job count."""
    q = _compute_scrape_quality(_result(jobs=[], error_code="parse_failure"), _adapter(0.95))
    assert q["score"] < 0.75


# ── Coverage signals ──────────────────────────────────────────────────────────

def test_description_coverage_full():
    jobs = [{"title": "Chef", "description": "Cook food.", "url": "https://boards.greenhouse.io/acme/1"}]
    q = _compute_scrape_quality(_result(jobs=jobs), _adapter(0.95))
    assert q["signals"]["description_coverage"] == 1.0


def test_description_coverage_partial():
    jobs = [
        {"title": "Chef", "snippet": "Cook.", "url": "https://boards.greenhouse.io/acme/1"},
        {"title": "Server", "url": "https://boards.greenhouse.io/acme/2"},
    ]
    q = _compute_scrape_quality(_result(jobs=jobs), _adapter(0.95))
    assert q["signals"]["description_coverage"] == 0.5


def test_url_coverage_unique_urls():
    jobs = [
        {"title": "Chef", "url": "https://boards.greenhouse.io/acme/1"},
        {"title": "Server", "url": "https://boards.greenhouse.io/acme/2"},
    ]
    q = _compute_scrape_quality(_result(jobs=jobs), _adapter(0.95))
    assert q["signals"]["url_coverage"] == 1.0


def test_url_coverage_all_listing_url():
    listing = "https://boards.greenhouse.io/acme"
    jobs = [
        {"title": "Chef", "url": listing},
        {"title": "Server", "url": listing},
    ]
    q = _compute_scrape_quality(_result(jobs=jobs, url=listing), _adapter(0.95))
    assert q["signals"]["url_coverage"] == 0.0


def test_coverage_zero_when_no_jobs():
    q = _compute_scrape_quality(_result(jobs=[]), _adapter(0.95))
    assert q["signals"]["description_coverage"] == 0.0
    assert q["signals"]["url_coverage"] == 0.0


# ── Low-confidence generic adapter ───────────────────────────────────────────

def test_generic_adapter_low_confidence_produces_low_grade():
    q = _compute_scrape_quality(_result(error_code="parse_failure"), _adapter(0.01))
    assert q["grade"] == "low"
    assert q["score"] < 0.45


# ── Result dict shape ─────────────────────────────────────────────────────────

def test_quality_dict_has_required_keys():
    q = _compute_scrape_quality(_result(), _adapter())
    assert "score" in q
    assert "grade" in q
    assert "signals" in q
    signals = q["signals"]
    for key in ("jobs_found", "adapter_confidence", "used_fallback", "fallback_depth",
                "error_code", "parse_method", "description_coverage", "url_coverage"):
        assert key in signals, f"missing signal: {key}"


def test_jsonld_method_is_depth_0():
    q = _compute_scrape_quality(
        _result(method="jsonld:detail_page", attempts=[{"method": "jsonld:detail_page"}]),
        _adapter(0.95),
    )
    assert q["signals"]["fallback_depth"] == 0
