"""Tests for tech stack detection."""
from app.tech_detect import detect_systems, _load_taxonomy, get_taxonomy_version


def test_taxonomy_loads():
    taxonomy = _load_taxonomy()
    assert len(taxonomy) >= 30
    assert all("system_id" in s for s in taxonomy)
    assert all("keywords" in s for s in taxonomy)
    assert get_taxonomy_version() == "1.1"


def test_detect_toast_in_html():
    html = '<div>We use Toast POS for our restaurant operations</div>'
    results = detect_systems(html)
    toast = [r for r in results if r["system_id"] == "toast"]
    assert len(toast) == 1
    assert toast[0]["category"] == "POS"
    assert toast[0]["confidence"] > 0
    assert "toast pos" in toast[0]["matched_keywords"]
    assert toast[0]["evidence"]


def test_detect_from_job_descriptions():
    html = '<div>Careers page</div>'
    jobs = [
        {"title": "Line Cook", "description": "Experience with Toast POS required"},
        {"title": "Accountant", "description": "Must know QuickBooks Online and Excel"},
    ]
    results = detect_systems(html, jobs)
    ids = {r["system_id"] for r in results}
    assert "toast" in ids
    assert "quickbooks" in ids


def test_no_false_positives():
    html = '<div>We are a great hotel with amazing rooms</div>'
    results = detect_systems(html)
    assert len(results) == 0


def test_confidence_increases_with_more_keywords():
    html = '<div>toast pos toasttab toast point of sale</div>'
    results = detect_systems(html)
    toast = [r for r in results if r["system_id"] == "toast"]
    assert len(toast) == 1
    assert toast[0]["confidence"] >= 1.0


def test_spreadsheet_detection():
    html = '<div>Currently tracking inventory in Excel spreadsheets</div>'
    results = detect_systems(html)
    manual = [r for r in results if r["system_id"] == "spreadsheets"]
    assert len(manual) >= 1
