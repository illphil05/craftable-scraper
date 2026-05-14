"""Tests for Harri adapter and parser."""
from app.site_adapters.harri import HarriAdapter
from app.site_adapters.workday import WorkdayAdapter
from app.parsers.harri import parse

HARRI_POSTING_URL = "https://app.harri.com/external/posting/12345"
HARRI_LISTING_URL = "https://app.harri.com/external/acmehotels/opening"


# ── Adapter matching ──────────────────────────────────────────────────────────

def test_harri_matches_posting():
    assert HarriAdapter().match_confidence(HARRI_POSTING_URL) >= 0.9


def test_harri_matches_listing():
    assert HarriAdapter().match_confidence(HARRI_LISTING_URL) >= 0.9


def test_workday_does_not_match_harri():
    assert WorkdayAdapter().match_confidence(HARRI_POSTING_URL) == 0.0


# ── Parser ────────────────────────────────────────────────────────────────────

_JSONLD_DETAIL_HTML = """
<html><body>
<script type="application/ld+json">
{
  "@type": "JobPosting",
  "title": "Hotel Controller",
  "url": "https://app.harri.com/external/posting/12345",
  "jobLocation": {
    "@type": "Place",
    "address": {"addressLocality": "Miami", "addressRegion": "FL"}
  }
}
</script>
</body></html>
"""

_CARD_HTML = """
<html><body>
  <div class="job-posting">
    <h3 class="job-title">Hotel Controller</h3>
    <span class="location">Miami, FL</span>
    <a href="/external/posting/12345">Apply</a>
  </div>
  <div class="job-posting">
    <h3 class="job-title">Director of Finance</h3>
    <span class="location">Atlanta, GA</span>
    <a href="/external/posting/12346">Apply</a>
  </div>
</body></html>
"""

_LINK_HTML = """
<html><body>
  <a href="/external/posting/12345">Hotel Controller</a>
  <a href="/external/opening/12346">Director of Finance</a>
  <a href="/home">Home</a>
</body></html>
"""


def test_parse_jsonld_detail():
    jobs = parse(_JSONLD_DETAIL_HTML, HARRI_POSTING_URL, "Acme Hotels")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Hotel Controller"
    assert jobs[0]["location"] == "Miami, FL"


def test_parse_job_cards():
    jobs = parse(_CARD_HTML, HARRI_LISTING_URL, "Acme Hotels")
    assert len(jobs) == 2
    titles = {j["title"] for j in jobs}
    assert "Hotel Controller" in titles


def test_parse_posting_links():
    jobs = parse(_LINK_HTML, HARRI_LISTING_URL, "Acme Hotels")
    assert len(jobs) == 2
    assert all("home" not in j["url"] for j in jobs)


def test_parse_empty():
    assert parse("<html><body></body></html>", HARRI_POSTING_URL) == []


def test_parse_sets_company_name():
    jobs = parse(_JSONLD_DETAIL_HTML, HARRI_POSTING_URL, "Acme Hotels & Resorts")
    assert jobs[0]["company_name"] == "Acme Hotels & Resorts"


def test_parse_relative_urls_resolved():
    jobs = parse(_LINK_HTML, HARRI_LISTING_URL, "Acme")
    for j in jobs:
        assert j["url"].startswith("http")
