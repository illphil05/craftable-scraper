"""Tests for Phase 4 job identity chain and lifecycle flags."""
import pytest

from app.db import _extract_ats_job_id, _compute_changed_fields, _job_content_hash


# ── _extract_ats_job_id ───────────────────────────────────────────────────────

def test_greenhouse_extracts_numeric_id():
    url = "https://boards.greenhouse.io/acmecorp/jobs/4567890"
    assert _extract_ats_job_id(url) == "4567890"


def test_lever_extracts_uuid():
    url = "https://jobs.lever.co/acmecorp/abc12345-dead-beef-cafe-000000000001"
    assert _extract_ats_job_id(url) == "abc12345-dead-beef-cafe-000000000001"


def test_ashby_extracts_uuid():
    url = "https://jobs.ashbyhq.com/acmecorp/12345678-1234-1234-1234-123456789012"
    assert _extract_ats_job_id(url) == "12345678-1234-1234-1234-123456789012"


def test_workable_extracts_code():
    url = "https://apply.workable.com/acmecorp/j/AB1C2D3E4F"
    assert _extract_ats_job_id(url) == "AB1C2D3E4F"


def test_jobvite_extracts_code():
    url = "https://jobs.jobvite.com/acmecorp/job/oTzagfw0"
    assert _extract_ats_job_id(url) == "oTzagfw0"


def test_non_ats_url_returns_none():
    assert _extract_ats_job_id("https://careers.acmecorp.com/jobs/chef") is None


def test_empty_url_returns_none():
    assert _extract_ats_job_id("") is None


def test_short_segment_returns_none():
    # Single-char or very short terminal segment is noise
    assert _extract_ats_job_id("https://boards.greenhouse.io/acme/jobs/ab") is None


# ── _compute_changed_fields ───────────────────────────────────────────────────

def test_no_change_when_identical():
    row = {"title": "Chef", "location": "NYC", "department": "F&B",
           "employment_type": None, "salary_text": None, "salary_min": None,
           "salary_max": None, "url": "https://example.com/job/1"}
    assert _compute_changed_fields(row, row) == []


def test_detects_title_change():
    existing = {"title": "Chef", "location": "NYC", "department": None,
                "employment_type": None, "salary_text": None, "salary_min": None,
                "salary_max": None, "url": "https://example.com/job/1"}
    new = {**existing, "title": "Senior Chef"}
    assert _compute_changed_fields(existing, new) == ["title"]


def test_detects_salary_change():
    existing = {"title": "Chef", "location": "NYC", "department": None,
                "employment_type": None, "salary_text": None, "salary_min": 50000,
                "salary_max": 70000, "url": "https://example.com/job/1"}
    new = {**existing, "salary_min": 60000}
    assert "salary_min" in _compute_changed_fields(existing, new)


def test_none_and_empty_string_treated_as_equal():
    existing = {"title": "Chef", "location": None, "department": None,
                "employment_type": None, "salary_text": None, "salary_min": None,
                "salary_max": None, "url": None}
    new = {**existing, "location": ""}
    assert _compute_changed_fields(existing, new) == []


# ── _job_content_hash ─────────────────────────────────────────────────────────

def test_hash_is_stable():
    h1 = _job_content_hash("co1", "Chef de Partie", "New York")
    h2 = _job_content_hash("co1", "Chef de Partie", "New York")
    assert h1 == h2


def test_hash_case_insensitive():
    h1 = _job_content_hash("co1", "CHEF", "NYC")
    h2 = _job_content_hash("co1", "chef", "nyc")
    assert h1 == h2


def test_hash_differs_by_company():
    h1 = _job_content_hash("co1", "Chef", "NYC")
    h2 = _job_content_hash("co2", "Chef", "NYC")
    assert h1 != h2


def test_hash_is_32_chars():
    assert len(_job_content_hash("co1", "Chef", "NYC")) == 32
