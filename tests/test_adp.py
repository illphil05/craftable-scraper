"""Tests for ADP Workforce Now adapter and parser."""
from app.site_adapters.adp import ADPAdapter
from app.site_adapters.workday import WorkdayAdapter
from app.parsers.adp import parse

ADP_URL = "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=abc&ccId=xyz"


# ── Adapter matching ──────────────────────────────────────────────────────────

def test_adp_matches_workforcenow():
    assert ADPAdapter().match_confidence(ADP_URL) >= 0.9


def test_workday_does_not_match_adp():
    assert WorkdayAdapter().match_confidence(ADP_URL) == 0.0


# ── Parser ────────────────────────────────────────────────────────────────────

_JSONLD_HTML = """
<html><body>
<script type="application/ld+json">
[
  {"@type": "JobPosting", "title": "Hotel Controller", "url": "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=abc&positionId=1"},
  {"@type": "JobPosting", "title": "Director of Finance", "url": "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=abc&positionId=2"}
]
</script>
</body></html>
"""

_CARD_HTML = """
<html><body>
  <div class="jobCard">
    <span class="jobTitle"><a href="?positionId=1">Hotel Controller</a></span>
    <span class="jobLocation">Miami, FL</span>
  </div>
  <div class="jobCard">
    <span class="jobTitle"><a href="?positionId=2">Director of Finance</a></span>
    <span class="jobLocation">Atlanta, GA</span>
  </div>
</body></html>
"""

_LINK_HTML = """
<html><body>
  <a href="?positionId=1">Hotel Controller</a>
  <a href="?positionId=2">Director of Finance</a>
  <a href="/login">Login</a>
</body></html>
"""


def test_parse_jsonld():
    jobs = parse(_JSONLD_HTML, ADP_URL, "Acme Corp")
    assert len(jobs) == 2
    assert any(j["title"] == "Hotel Controller" for j in jobs)


def test_parse_job_cards():
    jobs = parse(_CARD_HTML, ADP_URL, "Acme Corp")
    assert len(jobs) == 2
    miami = next(j for j in jobs if j["title"] == "Hotel Controller")
    assert miami["location"] == "Miami, FL"


def test_parse_position_links():
    jobs = parse(_LINK_HTML, ADP_URL, "Acme Corp")
    assert len(jobs) == 2
    assert all("login" not in j["url"].lower() for j in jobs)


def test_parse_empty():
    assert parse("<html><body></body></html>", ADP_URL) == []


def test_parse_sets_company_name():
    jobs = parse(_CARD_HTML, ADP_URL, "Acme Corp")
    assert all(j["company_name"] == "Acme Corp" for j in jobs)
