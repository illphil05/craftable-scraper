"""Tests for the dynamic parser (app/parsers/dynamic.py)."""
import json
import pytest
from app.parsers.dynamic import parse_dynamic, MIN_CONFIDENCE


# ── JSON-LD JobPosting ────────────────────────────────────────────────────────

def test_json_ld_single_jobposting():
    html = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "JobPosting",
      "title": "Front Desk Manager",
      "url": "https://example.com/jobs/front-desk-manager",
      "jobLocation": {"@type": "Place", "address": {"addressLocality": "New York", "addressRegion": "NY"}},
      "hiringOrganization": {"@type": "Organization", "name": "Example Hotel"}
    }
    </script>
    """
    jobs = parse_dynamic(html, "https://example.com/careers", "Example Hotel")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Front Desk Manager"
    assert jobs[0]["url"] == "https://example.com/jobs/front-desk-manager"
    assert jobs[0]["location"] == "New York, NY"
    assert jobs[0]["source_confidence"] == 0.95
    assert jobs[0]["extraction_method"] == "dynamic:json_ld"


def test_json_ld_list_of_jobpostings():
    postings = [
        {"@type": "JobPosting", "title": "Chef", "url": "https://example.com/jobs/1"},
        {"@type": "JobPosting", "title": "Server", "url": "https://example.com/jobs/2"},
    ]
    html = f'<script type="application/ld+json">{json.dumps(postings)}</script>'
    jobs = parse_dynamic(html, "https://example.com")
    assert len(jobs) == 2
    titles = {j["title"] for j in jobs}
    assert titles == {"Chef", "Server"}


def test_json_ld_graph_with_jobpostings():
    blob = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "name": "Acme"},
            {"@type": "JobPosting", "title": "Line Cook", "url": "https://example.com/jobs/3"},
        ],
    }
    html = f'<script type="application/ld+json">{json.dumps(blob)}</script>'
    jobs = parse_dynamic(html, "https://example.com")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Line Cook"


def test_json_ld_missing_title_skipped():
    blob = {"@type": "JobPosting", "url": "https://example.com/jobs/4"}
    html = f'<script type="application/ld+json">{json.dumps(blob)}</script>'
    jobs = parse_dynamic(html, "https://example.com")
    assert jobs == []


# ── __NEXT_DATA__ embedded state ─────────────────────────────────────────────

def test_next_data_embedded_jobs():
    state = {
        "props": {
            "pageProps": {
                "jobs": [
                    {"title": "Sous Chef", "url": "/jobs/sous-chef", "location": "Chicago"},
                    {"title": "Pastry Chef", "url": "/jobs/pastry-chef", "location": "Chicago"},
                ]
            }
        }
    }
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(state)}</script>'
    jobs = parse_dynamic(html, "https://restaurant.com/careers")
    assert len(jobs) == 2
    titles = {j["title"] for j in jobs}
    assert "Sous Chef" in titles
    assert jobs[0]["source_confidence"] == 0.85
    assert jobs[0]["extraction_method"] == "dynamic:embedded_state"


# ── Repeated job-card DOM patterns ────────────────────────────────────────────

def test_job_card_dom_pattern():
    html = """
    <ul>
      <li class="job-card">
        <h3 class="title">Bartender</h3>
        <a href="/jobs/bartender">Apply</a>
        <span class="location">Miami, FL</span>
      </li>
      <li class="job-card">
        <h3 class="title">Barback</h3>
        <a href="/jobs/barback">Apply</a>
        <span class="location">Miami, FL</span>
      </li>
      <li class="job-card">
        <h3 class="title">Host</h3>
        <a href="/jobs/host">Apply</a>
      </li>
    </ul>
    """
    jobs = parse_dynamic(html, "https://venue.com/careers")
    assert len(jobs) == 3
    titles = {j["title"] for j in jobs}
    assert "Bartender" in titles
    assert jobs[0]["source_confidence"] == 0.70


def test_job_card_dom_pattern_with_single_quoted_attributes():
    html = """
    <section>
      <article class='opening-card'>
        <h2 class='position-name'>Night Auditor</h2>
        <a href='/careers/night-auditor'>View role</a>
        <div class='job-location'>Denver, CO</div>
      </article>
      <article class='opening-card'>
        <h2 class='position-name'>Banquet Captain</h2>
        <a href='/careers/banquet-captain'>View role</a>
        <div class='job-location'>Denver, CO</div>
      </article>
    </section>
    """
    jobs = parse_dynamic(html, "https://unknown.example/careers", "Unknown Hotel")
    assert len(jobs) == 2
    assert jobs[0]["url"] == "https://unknown.example/careers/night-auditor"
    assert jobs[0]["location"] == "Denver, CO"
    assert jobs[0]["extraction_method"] == "dynamic:job_cards"


# ── Job-like anchors ──────────────────────────────────────────────────────────

def test_job_anchors_fallback():
    html = """
    <a href="https://example.com/careers/job/marketing-manager">Marketing Manager</a>
    <a href="https://example.com/careers/job/data-analyst">Data Analyst</a>
    <a href="https://example.com/">Home</a>
    """
    jobs = parse_dynamic(html, "https://example.com")
    assert len(jobs) == 2
    titles = {j["title"] for j in jobs}
    assert "Marketing Manager" in titles
    assert jobs[0]["source_confidence"] == 0.50


def test_job_anchors_fallback_with_single_quoted_href():
    html = """
    <a href='/positions/front-office-manager'>Front Office Manager</a>
    <a href='/opening/revenue-analyst'>Revenue Analyst</a>
    """
    jobs = parse_dynamic(html, "https://example.com/careers")
    assert {j["title"] for j in jobs} == {"Front Office Manager", "Revenue Analyst"}


# ── Confidence filtering ──────────────────────────────────────────────────────

def test_min_confidence_default_filters_below_50():
    """parse_dynamic with default min_confidence must return only >= 0.50 jobs."""
    html = """<p>No jobs here, just navigation links.</p>"""
    jobs = parse_dynamic(html, "https://example.com")
    assert jobs == []


def test_min_confidence_custom_threshold():
    """With a higher threshold, job-anchor results (0.50) are excluded."""
    html = """
    <a href="https://example.com/careers/job/receptionist">Receptionist</a>
    """
    # At default (0.50) this returns the job
    jobs_default = parse_dynamic(html, "https://example.com", min_confidence=0.50)
    assert len(jobs_default) >= 1

    # At 0.60 threshold the 0.50-confidence anchor is excluded
    jobs_high = parse_dynamic(html, "https://example.com", min_confidence=0.60)
    assert jobs_high == []


# ── Strategy priority ─────────────────────────────────────────────────────────

def test_json_ld_takes_priority_over_anchors():
    """JSON-LD strategy (0.95) must win even when anchors are present."""
    blob = {"@type": "JobPosting", "title": "Executive Chef", "url": "https://example.com/jobs/exec"}
    html = f"""
    <script type="application/ld+json">{json.dumps(blob)}</script>
    <a href="https://example.com/careers/job/random-job">Random Job From Anchor</a>
    """
    jobs = parse_dynamic(html, "https://example.com")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Executive Chef"
    assert jobs[0]["extraction_method"] == "dynamic:json_ld"
