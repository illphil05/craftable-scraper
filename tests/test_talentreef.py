"""Tests for TalentReef/JobAppNetwork adapter and parser."""
import pytest
from app.site_adapters.talentreef import TalentReefAdapter
from app.site_adapters.workday import WorkdayAdapter
from app.parsers.talentreef import parse

JOBAPPNETWORK_URL = "https://apply.jobappnetwork.com/clients/20594/"
TALENTREEF_URL = "https://crestline.talentreef.com/careers/"


# ── Adapter matching ──────────────────────────────────────────────────────────

def test_talentreef_adapter_matches_jobappnetwork():
    a = TalentReefAdapter()
    assert a.match_confidence(JOBAPPNETWORK_URL) >= 0.9


def test_talentreef_adapter_matches_talentreef_domain():
    a = TalentReefAdapter()
    assert a.match_confidence(TALENTREEF_URL) >= 0.9


def test_workday_does_not_match_jobappnetwork():
    w = WorkdayAdapter()
    assert w.match_confidence(JOBAPPNETWORK_URL) == 0.0


def test_workday_still_matches_its_own_urls():
    w = WorkdayAdapter()
    assert w.match_confidence("https://acme.myworkday.com/wday/authgwy/acme/login.htmld") >= 0.9
    assert w.match_confidence("https://wd3.myworkdayjobs.com/acme/jobs") >= 0.9


def test_workday_title_json_no_longer_triggers_false_match():
    # A page that has '"title"' in JSON but no Workday URL/markers
    html = '<html><script>{"title": "Finance Director"}</script></html>'
    w = WorkdayAdapter()
    assert w.match_confidence("https://apply.jobappnetwork.com/clients/123/", html=html) == 0.0


# ── Parser ────────────────────────────────────────────────────────────────────

_JSONLD_HTML = """
<html><body>
<script type="application/ld+json">
[
  {"@type": "JobPosting", "title": "Director of Finance", "url": "https://apply.jobappnetwork.com/clients/20594/en-US/job/12345"},
  {"@type": "JobPosting", "title": "Hotel Controller", "url": "https://apply.jobappnetwork.com/clients/20594/en-US/job/12346"}
]
</script>
</body></html>
"""

_CARD_HTML = """
<html><body>
  <div class="job-listing">
    <h3>Director of Finance</h3>
    <a href="/clients/20594/en-US/job/12345">Apply</a>
  </div>
  <div class="job-listing">
    <h3>Hotel Controller</h3>
    <a href="/clients/20594/en-US/job/12346">Apply</a>
  </div>
</body></html>
"""

_LINK_HTML = """
<html><body>
  <a href="/apply/12345/director-of-finance">Director of Finance</a>
  <a href="/apply/12346/hotel-controller">Hotel Controller</a>
  <a href="/about">About Us</a>
</body></html>
"""


def test_parse_jsonld():
    jobs = parse(_JSONLD_HTML, JOBAPPNETWORK_URL, "Crestline")
    assert len(jobs) == 2
    assert jobs[0]["title"] == "Director of Finance"
    assert "12345" in jobs[0]["url"]


def test_parse_job_cards():
    jobs = parse(_CARD_HTML, JOBAPPNETWORK_URL, "Crestline")
    assert len(jobs) == 2
    titles = {j["title"] for j in jobs}
    assert "Director of Finance" in titles
    assert "Hotel Controller" in titles


def test_parse_apply_links():
    jobs = parse(_LINK_HTML, JOBAPPNETWORK_URL, "Crestline")
    assert len(jobs) == 2
    assert all("about" not in j["url"] for j in jobs)


def test_parse_empty_html():
    assert parse("<html><body></body></html>", JOBAPPNETWORK_URL) == []


def test_parse_deduplicates():
    dupe = _JSONLD_HTML + _JSONLD_HTML
    jobs = parse(dupe, JOBAPPNETWORK_URL, "Crestline")
    titles = [j["title"] for j in jobs]
    assert len(titles) == len(set(t.lower() for t in titles))


def test_parse_sets_company_name():
    jobs = parse(_CARD_HTML, JOBAPPNETWORK_URL, "Crestline Hotels & Resorts")
    assert all(j["company_name"] == "Crestline Hotels & Resorts" for j in jobs)
