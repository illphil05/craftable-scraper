import json
import pytest
from app.parsers.paycom import parse
from app.site_adapters.paycom import PaycomAdapter

PORTAL_KEY = "BD425C8DA3F0DF46FBB223E4EE118FDB"

def make_job(**overrides):
    job = {
        "jobId": 12345,
        "jobTitle": "Restaurant Manager",
        "positionType": "Full-Time",
        "remoteType": "On-Site",
        "locations": "San Diego, CA",
        "description": "<p>Preview text</p>",
        "postedOn": "2024-01-15T00:00:00",
        "isHotJob": False,
        "city": "San Diego",
        "salaryRange": "$50k",
        "jobCategory": "Food & Beverage",
        "educationLevel": "Bachelor",
        "description_full": "<p>Full description here</p>",
        "qualifications": "<p>Quals</p>",
    }
    job.update(overrides)
    return job

def make_payload(jobs=None, company_name="Hilton Bayfront", portal_key=PORTAL_KEY):
    return json.dumps({
        "jobs": jobs if jobs is not None else [make_job()],
        "company_name": company_name,
        "portal_key": portal_key,
    })


def test_parse_maps_job_correctly():
    result = parse(make_payload(), url="https://example.com", company_name="Hilton Bayfront")
    assert len(result) == 1
    job = result[0]
    assert job["title"] == "Restaurant Manager"
    assert job["company_name"] == "Hilton Bayfront"
    assert job["url"] == f"https://www.paycomonline.net/v4/ats/web.php/portal/{PORTAL_KEY}/career-page#/jobs/12345"
    assert job["location"] == "San Diego"
    assert job["snippet"] == "Full description here"
    assert job["department"] == "Food & Beverage"


def test_parse_uses_city_over_locations():
    result = parse(make_payload([make_job(city="San Diego", locations="San Diego, CA")]),
                   url="", company_name="")
    assert result[0]["location"] == "San Diego"

    result = parse(make_payload([make_job(city="", locations="San Diego, CA")]),
                   url="", company_name="")
    assert result[0]["location"] == "San Diego, CA"


def test_parse_strips_html_from_snippet():
    result = parse(make_payload([make_job(description_full="<p>Full <b>description</b> here</p>")]),
                   url="", company_name="")
    assert "<" not in result[0]["snippet"]
    assert "Full description here" in result[0]["snippet"]


def test_parse_snippet_fallback():
    result = parse(make_payload([make_job(description_full="", description="<p>Preview only</p>")]),
                   url="", company_name="")
    assert "Preview only" in result[0]["snippet"]
    assert "<" not in result[0]["snippet"]


def test_parse_empty_jobs_list():
    payload = json.dumps({"jobs": [], "company_name": "X", "portal_key": PORTAL_KEY})
    result = parse(payload, url="", company_name="")
    assert result == []


def test_parse_non_json_html():
    result = parse("<html>not json</html>", url="", company_name="")
    assert result == []


def test_parse_skips_job_with_no_title():
    result = parse(make_payload([make_job(jobTitle="")]), url="", company_name="")
    assert result == []


def test_parse_deduplicates():
    job = make_job()
    result = parse(make_payload([job, job]), url="", company_name="")
    assert len(result) == 1


def test_adapter_confidence_paycom_url():
    url = f"https://www.paycomonline.net/v4/ats/web.php/portal/{PORTAL_KEY}/career-page"
    confidence = PaycomAdapter().match_confidence(url)
    assert confidence >= 0.95


def test_adapter_confidence_other_url():
    confidence = PaycomAdapter().match_confidence("https://careers.example.com/jobs")
    assert confidence < 0.5
