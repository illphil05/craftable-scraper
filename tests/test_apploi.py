"""Tests for Apploi adapter and parser."""
from app.site_adapters.apploi import ApploiAdapter
from app.site_adapters.workday import WorkdayAdapter
from app.parsers.apploi import parse

APPLOI_URL = "https://apploi.com/job/12345"


# ── Adapter matching ──────────────────────────────────────────────────────────

def test_apploi_matches_job_url():
    assert ApploiAdapter().match_confidence(APPLOI_URL) >= 0.9


def test_apploi_matches_apply_url():
    assert ApploiAdapter().match_confidence("https://apploi.com/apply/67890") >= 0.9


def test_workday_does_not_match_apploi():
    assert WorkdayAdapter().match_confidence(APPLOI_URL) == 0.0


# ── Parser ────────────────────────────────────────────────────────────────────

_JSONLD_HTML = """
<html><body>
<script type="application/ld+json">
{
  "@type": "JobPosting",
  "title": "Hotel Controller",
  "description": "Manage financial operations.",
  "jobLocation": {"@type": "Place", "address": {"addressLocality": "Miami", "addressRegion": "FL"}},
  "hiringOrganization": {"name": "Acme Hotels"}
}
</script>
</body></html>
"""

_H1_HTML = """
<html><body>
  <h1 class="job-title">Hotel Controller</h1>
  <span class="location">Miami, FL</span>
</body></html>
"""

_OG_HTML = """
<html>
<head>
  <meta property="og:title" content="Hotel Controller - Acme Hotels" />
</head>
<body></body></html>
"""


def test_parse_jsonld():
    jobs = parse(_JSONLD_HTML, APPLOI_URL, "Acme Hotels")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Hotel Controller"
    assert jobs[0]["location"] == "Miami, FL"


def test_parse_jsonld_uses_hiring_org_when_no_company_name():
    jobs = parse(_JSONLD_HTML, APPLOI_URL, None)
    assert jobs[0]["company_name"] == "Acme Hotels"


def test_parse_h1():
    jobs = parse(_H1_HTML, APPLOI_URL, "Acme Hotels")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Hotel Controller"
    assert jobs[0]["location"] == "Miami, FL"


def test_parse_og_title_strips_company():
    jobs = parse(_OG_HTML, APPLOI_URL, "Acme Hotels")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Hotel Controller"


def test_parse_empty():
    assert parse("<html><body></body></html>", APPLOI_URL) == []


def test_parse_sets_company_name():
    jobs = parse(_H1_HTML, APPLOI_URL, "Acme Hotels & Resorts")
    assert jobs[0]["company_name"] == "Acme Hotels & Resorts"
