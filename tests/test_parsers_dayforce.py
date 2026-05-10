import json
import pytest
from app.parsers.dayforce import parse

URL = "https://jobs.dayforcehcm.com/en-US/ohmc/CANDIDATEPORTAL/jobs/6570"


def make_next_data(job_data=None, include_job_data=True):
    page_props = {}
    if include_job_data:
        page_props["jobData"] = job_data if job_data is not None else make_job_data()
    return json.dumps({"props": {"pageProps": page_props}})


def make_job_data(**overrides):
    data = {
        "jobTitle": "Registered Nurse",
        "jobReqId": "RN-2024-001",
        "jobPostingId": 6570,
        "postingStatus": 1,
        "postingLocations": [{"name": "Columbus, OH"}, {"name": "Dublin, OH"}],
        "jobPostingContent": {
            "jobDescription": "<p>Care for patients.</p><br><p>Join our team.</p>"
        },
        "postingStartTimestampUTC": "2024-03-15T00:00:00Z",
    }
    data.update(overrides)
    return data


def wrap_html(next_data_json: str) -> str:
    return f'<html><body><script id="__NEXT_DATA__" type="application/json">{next_data_json}</script></body></html>'


# ── Happy path ────────────────────────────────────────────────────────────────

def test_valid_job_extracts_all_fields():
    html = wrap_html(make_next_data())
    result = parse(html, URL, company_name="OHMC")
    assert len(result) == 1
    job = result[0]
    assert job["title"] == "Registered Nurse"
    assert job["company_name"] == "OHMC"
    assert job["url"] == URL
    assert job["location"] == "Columbus, OH; Dublin, OH"
    assert job["requisition_id"] == "RN-2024-001"
    assert job["posted_date"] == "2024-03-15"


def test_description_is_plain_text_not_html():
    html = wrap_html(make_next_data())
    job = parse(html, URL)[0]
    assert "<p>" not in (job["description"] or "")
    assert "<br>" not in (job["description"] or "")
    assert "Care for patients." in job["description"]
    assert "Join our team." in job["description"]


def test_block_tags_preserve_word_separation():
    job_data = make_job_data(
        jobPostingContent={"jobDescription": "<p>First paragraph</p><p>Second paragraph</p>"}
    )
    html = wrap_html(make_next_data(job_data))
    job = parse(html, URL)[0]
    assert "FirstSecond" not in job["description"]
    assert "First paragraph" in job["description"]
    assert "Second paragraph" in job["description"]


def test_br_tag_preserves_word_separation():
    job_data = make_job_data(
        jobPostingContent={"jobDescription": "Word A<br>Word B"}
    )
    html = wrap_html(make_next_data(job_data))
    job = parse(html, URL)[0]
    assert "AWord" not in job["description"]


def test_snippet_is_truncated_to_500_chars():
    long_text = "x" * 600
    job_data = make_job_data(
        jobPostingContent={"jobDescription": f"<p>{long_text}</p>"}
    )
    html = wrap_html(make_next_data(job_data))
    job = parse(html, URL)[0]
    assert len(job["snippet"]) == 500


def test_company_name_falls_back_to_empty_string():
    html = wrap_html(make_next_data())
    job = parse(html, URL)
    assert job[0]["company_name"] == ""


# ── Soft failures ─────────────────────────────────────────────────────────────

def test_expired_job_returns_empty_list():
    job_data = make_job_data(postingStatus=4)
    html = wrap_html(make_next_data(job_data))
    assert parse(html, URL) == []


def test_missing_next_data_returns_empty_list():
    assert parse("<html><body><p>No data here</p></body></html>", URL) == []


def test_listing_page_shape_without_job_data_returns_empty_list():
    # Listing pages have pageProps but no jobData key
    html = wrap_html(make_next_data(include_job_data=False))
    assert parse(html, URL) == []


def test_malformed_json_returns_empty_list():
    html = '<html><body><script id="__NEXT_DATA__">{bad json</script></body></html>'
    assert parse(html, URL) == []


def test_missing_title_returns_empty_list():
    job_data = make_job_data(jobTitle=None)
    html = wrap_html(make_next_data(job_data))
    assert parse(html, URL) == []


# ── Optional field handling ───────────────────────────────────────────────────

def test_no_locations_yields_none():
    job_data = make_job_data(postingLocations=[])
    html = wrap_html(make_next_data(job_data))
    job = parse(html, URL)[0]
    assert job["location"] is None


def test_missing_description_yields_none_snippet_and_description():
    job_data = make_job_data(jobPostingContent={})
    html = wrap_html(make_next_data(job_data))
    job = parse(html, URL)[0]
    assert job["description"] is None
    assert job["snippet"] is None


def test_missing_req_id_yields_none():
    job_data = make_job_data(jobReqId=None)
    html = wrap_html(make_next_data(job_data))
    job = parse(html, URL)[0]
    assert job["requisition_id"] is None


def test_missing_posted_date_yields_none():
    job_data = make_job_data(postingStartTimestampUTC=None)
    html = wrap_html(make_next_data(job_data))
    job = parse(html, URL)[0]
    assert job["posted_date"] is None
