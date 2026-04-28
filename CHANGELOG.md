# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0.0] - 2026-04-28

### Added

- **Intelligence extraction layer**: new `app/intelligence/` module detects hospitality
  tech systems (regex against a 40-entry taxonomy) and extracts ops/finance signal phrases
  from job descriptions using Claude Haiku LLM calls
- **Enrichment queue**: jobs are enriched at most once (or up to 3 retries on failure)
  via explicit `enriched_at` + `enrichment_attempts` columns — replaces the previous
  bullet-absence gate that caused infinite retry loops
- **Company-level intelligence rollup**: `_aggregate_company_intelligence` rolls per-job
  signals into `company_intelligence` table after each successful enrichment
- **Intelligence API routes**: `GET /api/intelligence/companies`, `GET /api/intelligence/companies/{name}`,
  `GET /api/intelligence/digest/daily` (new/surging companies), `POST /api/intelligence/enrich/{job_id}`
  with idempotency check and `force` override
- **Paycom ATS adapter**: API-capture strategy scrapes Paycom-hosted career pages via
  network interception; includes dedicated parser and 119-line test suite
- **DB migrations**: `enriched_at`, `enrichment_attempts`, `enrichment_failed_at` columns
  added to `jobs`; `job_systems`, `job_intelligence_bullets`, `company_intelligence` tables

### Fixed

- `content_hash` pre-flight migration prevents startup crash when upgrading existing databases
- LLM API errors now propagate correctly so batch enrichment marks failures instead
  of silently storing empty bullets (jobs now retry up to 3× on transient errors)
- Anthropic client reused as a module-level singleton rather than instantiated per call
  (fixes connection pool leak under batch enrichment)

### Changed

- Enrichment queue now uses `COALESCE(description, snippet)` for richer text content
- `extract_bullets` validates LLM output shape and caps bullets at 50 per job
