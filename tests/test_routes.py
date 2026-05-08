from app.routes import SaveScrapeRequest, _company_website_from_careers_url


def test_save_scrape_request_uses_independent_mutable_defaults():
    first = SaveScrapeRequest(
        careers_url="https://example.com/careers",
        parser_used="playwright:generic",
        jobs_found=0,
        elapsed_ms=1,
    )
    second = SaveScrapeRequest(
        careers_url="https://example.com/careers",
        parser_used="playwright:generic",
        jobs_found=0,
        elapsed_ms=1,
    )

    first.artifact_refs["html_size"] = 100
    first.jobs.append({"title": "Chef"})

    assert second.artifact_refs == {}
    assert second.jobs == []


# ── _company_website_from_careers_url ─────────────────────────────────────────

def test_derives_origin_from_company_owned_careers_subdomain():
    assert _company_website_from_careers_url("https://careers.acmehotel.com/jobs/123") \
        == "https://careers.acmehotel.com"

def test_strips_path_and_query():
    assert _company_website_from_careers_url("https://www.hilton.com/en/careers?region=us") \
        == "https://www.hilton.com"

def test_returns_none_for_greenhouse():
    assert _company_website_from_careers_url("https://boards.greenhouse.io/acme/jobs/123") is None

def test_returns_none_for_lever():
    assert _company_website_from_careers_url("https://jobs.lever.co/marriott/abc-uuid") is None

def test_returns_none_for_workday():
    assert _company_website_from_careers_url("https://hilton.wd1.myworkdayjobs.com/en-US/HiltonHotels") is None

def test_returns_none_for_ashby():
    assert _company_website_from_careers_url("https://jobs.ashbyhq.com/acme/abc-uuid") is None

def test_returns_none_when_careers_url_is_none():
    assert _company_website_from_careers_url(None) is None

def test_returns_none_for_invalid_url():
    assert _company_website_from_careers_url("not-a-url") is None

def test_prefers_explicit_website_url_via_caller():
    # The helper only derives — callers pass explicit website_url when available.
    # Verify that a known-good URL passes through as-is.
    result = _company_website_from_careers_url("https://careers.marriott.com/jobs/1234")
    assert result == "https://careers.marriott.com"
