"""Tests for JazzHR adapter and parser."""
from app.site_adapters.jazzhr import JazzHRAdapter
from app.site_adapters.lever import LeverAdapter
from app.parsers.jazzhr import parse

APPLYTOJOB_URL = "https://acme.applytojob.com/apply/"
JAZZ_URL = "https://app.jazz.co/apply/acme"


# ── Adapter matching ──────────────────────────────────────────────────────────

def test_jazzhr_matches_applytojob():
    assert JazzHRAdapter().match_confidence(APPLYTOJOB_URL) >= 0.9


def test_jazzhr_matches_jazz_co():
    assert JazzHRAdapter().match_confidence(JAZZ_URL) >= 0.9


def test_lever_does_not_match_applytojob():
    assert LeverAdapter().match_confidence(APPLYTOJOB_URL) == 0.0


# ── Parser ────────────────────────────────────────────────────────────────────

_JSONLD_HTML = """
<html><body>
<script type="application/ld+json">
[
  {"@type": "JobPosting", "title": "Hotel Controller", "url": "https://acme.applytojob.com/apply/abc/Hotel-Controller"},
  {"@type": "JobPosting", "title": "Director of Finance", "url": "https://acme.applytojob.com/apply/def/Director-of-Finance"}
]
</script>
</body></html>
"""

_CARD_HTML = """
<html><body>
  <div id="openings">
    <div class="opening">
      <h5 class="opening-job-title"><a href="/apply/abc/Hotel-Controller">Hotel Controller</a></h5>
      <p class="opening-department">Finance</p>
      <p class="opening-location">Miami, FL</p>
    </div>
    <div class="opening">
      <h5 class="opening-job-title"><a href="/apply/def/Director-of-Finance">Director of Finance</a></h5>
      <p class="opening-department">Finance</p>
      <p class="opening-location">Atlanta, GA</p>
    </div>
  </div>
</body></html>
"""

_LINK_HTML = """
<html><body>
  <a href="/apply/abc/Hotel-Controller">Hotel Controller</a>
  <a href="/apply/def/Director-of-Finance">Director of Finance</a>
  <a href="/about">About Us</a>
</body></html>
"""


def test_parse_jsonld():
    jobs = parse(_JSONLD_HTML, APPLYTOJOB_URL, "Acme Hotels")
    assert len(jobs) == 2
    assert jobs[0]["title"] == "Hotel Controller"
    assert "abc" in jobs[0]["url"]


def test_parse_opening_cards():
    jobs = parse(_CARD_HTML, APPLYTOJOB_URL, "Acme Hotels")
    assert len(jobs) == 2
    titles = {j["title"] for j in jobs}
    assert "Hotel Controller" in titles
    assert "Director of Finance" in titles
    # location extracted from card
    miami = next(j for j in jobs if j["title"] == "Hotel Controller")
    assert miami["location"] == "Miami, FL"
    assert miami["department"] == "Finance"


def test_parse_apply_links():
    jobs = parse(_LINK_HTML, APPLYTOJOB_URL, "Acme Hotels")
    assert len(jobs) == 2
    assert all("about" not in j["url"] for j in jobs)


def test_parse_empty():
    assert parse("<html><body></body></html>", APPLYTOJOB_URL) == []


def test_parse_deduplicates():
    jobs = parse(_JSONLD_HTML + _JSONLD_HTML, APPLYTOJOB_URL, "Acme Hotels")
    titles = [j["title"] for j in jobs]
    assert len(titles) == len(set(t.lower() for t in titles))


def test_parse_sets_company_name():
    jobs = parse(_CARD_HTML, APPLYTOJOB_URL, "Acme Hotels & Resorts")
    assert all(j["company_name"] == "Acme Hotels & Resorts" for j in jobs)


def test_parse_relative_urls_resolved():
    jobs = parse(_CARD_HTML, APPLYTOJOB_URL, "Acme")
    for j in jobs:
        assert j["url"].startswith("http")
