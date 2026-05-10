"""Smoke tests for the four new ATS parsers: Ashby, Workable, Jobvite, Taleo."""
import json
import pytest


# ── Ashby ─────────────────────────────────────────────────────────────────────

ASHBY_URL = "https://jobs.ashbyhq.com/acmecorp"

def _ashby_html(postings):
    data = {
        "props": {
            "pageProps": {
                "jobBoard": {
                    "jobPostings": postings
                }
            }
        }
    }
    blob = json.dumps(data)
    return f'<html><script id="__NEXT_DATA__" type="application/json">{blob}</script></html>'


def test_ashby_returns_jobs():
    from app.parsers.ashby import parse
    html = _ashby_html([
        {"title": "Chef de Partie", "id": "abc-123", "locationName": "New York, NY", "departmentName": "Kitchen"},
        {"title": "Front Desk Agent", "id": "def-456", "locationName": "Miami, FL", "departmentName": "Front Office"},
    ])
    jobs = parse(html, ASHBY_URL, company_name="Acme Corp")
    assert len(jobs) == 2
    assert jobs[0]["title"] == "Chef de Partie"
    assert jobs[0]["url"] == "https://jobs.ashbyhq.com/acmecorp/abc-123"
    assert jobs[0]["location"] == "New York, NY"
    assert jobs[0]["department"] == "Kitchen"
    assert jobs[0]["company_name"] == "Acme Corp"


def test_ashby_missing_next_data_returns_empty():
    from app.parsers.ashby import parse
    jobs = parse("<html><body>No jobs here</body></html>", ASHBY_URL)
    assert jobs == []


def test_ashby_skips_posting_with_no_title():
    from app.parsers.ashby import parse
    html = _ashby_html([
        {"title": "", "id": "no-title"},
        {"title": "Sous Chef", "id": "xyz-789", "locationName": "Chicago, IL"},
    ])
    jobs = parse(html, ASHBY_URL)
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Sous Chef"


def test_ashby_null_optional_fields():
    from app.parsers.ashby import parse
    html = _ashby_html([{"title": "Dishwasher", "id": "dish-1"}])
    jobs = parse(html, ASHBY_URL)
    assert jobs[0]["location"] is None
    assert jobs[0]["department"] is None


# ── Workable ──────────────────────────────────────────────────────────────────

WORKABLE_URL = "https://apply.workable.com/hotelgroup"

def _workable_html(jobs_data):
    """Build minimal Workable HTML with job-title h3 and location span."""
    items = ""
    for j in jobs_data:
        items += (
            f'<div data-ui="job-summary">'
            f'<h3 class="job-title">{j["title"]}</h3>'
            f'<span class="location">{j.get("location", "")}</span>'
            f'<a href="{j["url"]}">Apply</a>'
            f'</div>'
        )
    return f"<html><body>{items}</body></html>"


def test_workable_returns_jobs():
    from app.parsers.workable import parse
    html = _workable_html([
        {"title": "Barista", "location": "Seattle, WA", "url": "https://apply.workable.com/hotelgroup/j/ABC123/"},
        {"title": "Housekeeper", "location": "Portland, OR", "url": "https://apply.workable.com/hotelgroup/j/DEF456/"},
    ])
    jobs = parse(html, WORKABLE_URL, company_name="Hotel Group")
    assert len(jobs) == 2
    assert jobs[0]["title"] == "Barista"
    assert jobs[0]["url"] == "https://apply.workable.com/hotelgroup/j/ABC123/"
    assert jobs[0]["location"] == "Seattle, WA"
    assert jobs[0]["company_name"] == "Hotel Group"


def test_workable_empty_html_returns_empty():
    from app.parsers.workable import parse
    jobs = parse("<html><body></body></html>", WORKABLE_URL)
    assert jobs == []


def test_workable_url_falls_back_to_page_url_when_no_href():
    from app.parsers.workable import parse
    html = (
        '<html><body>'
        '<div data-ui="job-summary"><h3 class="job-title">Cook</h3>'
        '<span class="location">Austin, TX</span></div>'
        '</body></html>'
    )
    jobs = parse(html, WORKABLE_URL)
    assert len(jobs) == 1
    assert jobs[0]["url"] == WORKABLE_URL


# ── Jobvite ───────────────────────────────────────────────────────────────────

JOBVITE_URL = "https://jobs.jobvite.com/marriott"

def _jobvite_html(jobs_data):
    items = ""
    for j in jobs_data:
        items += (
            f'<li class="jv-job-list-item">'
            f'<a href="{j["href"]}" class="jv-job-list-name">{j["title"]}</a>'
            f'<span class="jv-job-list-location">{j.get("location", "")}</span>'
            f'</li>'
        )
    return f'<html><body><ul class="jv-job-list">{items}</ul></body></html>'


def test_jobvite_returns_jobs():
    from app.parsers.jobvite import parse
    html = _jobvite_html([
        {"title": "Front Desk Supervisor", "href": "/marriott/careers/jobs/ABC123", "location": "Las Vegas, NV"},
        {"title": "Room Attendant", "href": "/marriott/careers/jobs/DEF456", "location": "Orlando, FL"},
    ])
    jobs = parse(html, JOBVITE_URL, company_name="Marriott")
    assert len(jobs) == 2
    assert jobs[0]["title"] == "Front Desk Supervisor"
    assert jobs[0]["url"] == "https://jobs.jobvite.com/marriott/careers/jobs/ABC123"
    assert jobs[0]["location"] == "Las Vegas, NV"
    assert jobs[0]["company_name"] == "Marriott"


def test_jobvite_empty_returns_empty():
    from app.parsers.jobvite import parse
    jobs = parse("<html><body></body></html>", JOBVITE_URL)
    assert jobs == []


def test_jobvite_skips_empty_title():
    from app.parsers.jobvite import parse
    html = (
        '<ul>'
        '<li><a href="/co/jobs/001" class="jv-job-list-name">  </a></li>'
        '<li><a href="/co/jobs/002" class="jv-job-list-name">Concierge</a></li>'
        '</ul>'
    )
    jobs = parse(html, JOBVITE_URL)
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Concierge"


# ── Taleo ─────────────────────────────────────────────────────────────────────

TALEO_URL = "https://hilton.taleo.net/careersection/2/joblist.ftl"

def _taleo_html(jobs_data):
    rows = ""
    for j in jobs_data:
        rows += (
            f'<tr>'
            f'<td><a href="{j["href"]}" class="jobTitle">{j["title"]}</a></td>'
            f'<td><span class="jobLocation">{j.get("location", "")}</span></td>'
            f'</tr>'
        )
    return f'<html><body><table class="requisitionListInterface">{rows}</table></body></html>'


def test_taleo_returns_jobs():
    from app.parsers.taleo import parse
    html = _taleo_html([
        {"title": "Guest Services Agent", "href": "/careersection/2/jobdetail.ftl?job=001", "location": "New York, NY"},
        {"title": "Banquet Server", "href": "/careersection/2/jobdetail.ftl?job=002", "location": "Chicago, IL"},
    ])
    jobs = parse(html, TALEO_URL, company_name="Hilton")
    assert len(jobs) == 2
    assert jobs[0]["title"] == "Guest Services Agent"
    assert jobs[0]["url"] == "https://hilton.taleo.net/careersection/2/jobdetail.ftl?job=001"
    assert jobs[0]["location"] == "New York, NY"
    assert jobs[0]["company_name"] == "Hilton"


def test_taleo_empty_returns_empty():
    from app.parsers.taleo import parse
    jobs = parse("<html><body></body></html>", TALEO_URL)
    assert jobs == []


def test_taleo_absolute_href_preserved():
    from app.parsers.taleo import parse
    html = (
        '<table><tr>'
        '<td><a href="https://hilton.taleo.net/careersection/2/jobdetail.ftl?job=999" class="jobTitle">Night Auditor</a></td>'
        '<td><span class="jobLocation">Austin, TX</span></td>'
        '</tr></table>'
    )
    jobs = parse(html, TALEO_URL)
    assert jobs[0]["url"] == "https://hilton.taleo.net/careersection/2/jobdetail.ftl?job=999"


def test_taleo_null_location_when_absent():
    from app.parsers.taleo import parse
    html = '<table><tr><td><a href="/jobs/001" class="jobTitle">Bartender</a></td></tr></table>'
    jobs = parse(html, TALEO_URL)
    assert jobs[0]["location"] is None
