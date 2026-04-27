from app.routes import SaveScrapeRequest


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
