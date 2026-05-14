"""Tests for BambooHR adapter and parser."""
from app.site_adapters.bamboohr import BambooHRAdapter
from app.site_adapters.workday import WorkdayAdapter
from app.parsers.bamboohr import parse

BAMBOOHR_URL = "https://crestline.bamboohr.com/jobs/"
BAMBOOHR_DETAIL_URL = "https://crestline.bamboohr.com/jobs/view.php?id=123"


# ── Adapter matching ──────────────────────────────────────────────────────────

def test_bamboohr_matches_listing():
    assert BambooHRAdapter().match_confidence(BAMBOOHR_URL) >= 0.9


def test_bamboohr_matches_detail():
    assert BambooHRAdapter().match_confidence(BAMBOOHR_DETAIL_URL) >= 0.9


def test_workday_does_not_match_bamboohr():
    assert WorkdayAdapter().match_confidence(BAMBOOHR_URL) == 0.0


# ── Parser ────────────────────────────────────────────────────────────────────

_JSONLD_HTML = """
<html><body>
<script type="application/ld+json">
{"@type": "JobPosting", "title": "Hotel Controller", "url": "https://crestline.bamboohr.com/jobs/view.php?id=101"}
</script>
</body></html>
"""

_NEW_UI_HTML = """
<html><body>
  <ul>
    <li class="BambooHR-ATS-Jobs-item">
      <a class="BambooHR-ATS-Jobs-item-title" href="/jobs/view.php?id=101">Hotel Controller</a>
      <span class="BambooHR-ATS-Jobs-item-location">Miami, FL</span>
      <span class="BambooHR-ATS-Jobs-item-department">Finance</span>
    </li>
    <li class="BambooHR-ATS-Jobs-item">
      <a class="BambooHR-ATS-Jobs-item-title" href="/jobs/view.php?id=102">Director of Finance</a>
      <span class="BambooHR-ATS-Jobs-item-location">Atlanta, GA</span>
    </li>
  </ul>
</body></html>
"""

_CLASSIC_TABLE_HTML = """
<html><body>
  <table class="ResposiveTable">
    <tbody>
      <tr><td><a href="/jobs/view.php?id=101">Hotel Controller</a></td><td>Miami, FL</td><td>Finance</td></tr>
      <tr><td><a href="/jobs/view.php?id=102">Director of Finance</a></td><td>Atlanta, GA</td><td>Finance</td></tr>
    </tbody>
  </table>
</body></html>
"""

_LINK_HTML = """
<html><body>
  <a href="/jobs/view.php?id=101">Hotel Controller</a>
  <a href="/jobs/view.php?id=102">Director of Finance</a>
  <a href="/about">About</a>
</body></html>
"""


def test_parse_jsonld():
    jobs = parse(_JSONLD_HTML, BAMBOOHR_URL, "Crestline")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Hotel Controller"


def test_parse_new_ui():
    jobs = parse(_NEW_UI_HTML, BAMBOOHR_URL, "Crestline")
    assert len(jobs) == 2
    titles = {j["title"] for j in jobs}
    assert "Hotel Controller" in titles
    miami = next(j for j in jobs if j["title"] == "Hotel Controller")
    assert miami["location"] == "Miami, FL"
    assert miami["department"] == "Finance"


def test_parse_classic_table():
    jobs = parse(_CLASSIC_TABLE_HTML, BAMBOOHR_URL, "Crestline")
    assert len(jobs) == 2
    assert jobs[0]["location"] == "Miami, FL"
    assert jobs[0]["department"] == "Finance"


def test_parse_view_php_links():
    jobs = parse(_LINK_HTML, BAMBOOHR_URL, "Crestline")
    assert len(jobs) == 2
    assert all("about" not in j["url"] for j in jobs)


def test_parse_empty():
    assert parse("<html><body></body></html>", BAMBOOHR_URL) == []


def test_parse_deduplicates():
    jobs = parse(_NEW_UI_HTML + _NEW_UI_HTML, BAMBOOHR_URL, "Crestline")
    titles = [j["title"] for j in jobs]
    assert len(titles) == len(set(t.lower() for t in titles))


def test_parse_sets_company_name():
    jobs = parse(_NEW_UI_HTML, BAMBOOHR_URL, "Crestline Hotels")
    assert all(j["company_name"] == "Crestline Hotels" for j in jobs)


def test_parse_relative_urls_resolved():
    jobs = parse(_CLASSIC_TABLE_HTML, BAMBOOHR_URL, "Crestline")
    for j in jobs:
        assert j["url"].startswith("http")
