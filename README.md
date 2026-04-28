# Craftable Scraper Service

Standalone Python/FastAPI microservice that scrapes JS-rendered ATS careers pages using Playwright + Chromium, returns structured job listings via REST API, and enriches them with hospitality tech stack intelligence using Claude Haiku.

The scraper uses an auto-discovered site adapter layer so ATS families stay isolated from the shared browser engine, persistence, and signal-detection framework.

## Why

Craftable Outreach's bundled scraper (Alpine + Node.js) cannot run a headless browser. JS-rendered ATS platforms (Paylocity, iCIMS, Workday, Paycom) return empty HTML to simple HTTP fetches. This service handles those pages and layers intelligence on top.

## Endpoints

### `GET /health`

Liveness check.

```bash
curl https://scraper.myrtle.cloud/health
```

### `POST /scrape`

Scrape a careers page. Requires `X-API-Key` header.

```bash
curl -X POST https://scraper.myrtle.cloud/scrape \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <SCRAPER_API_KEY>" \
  -d '{"url":"https://recruiting.paylocity.com/Recruiting/Jobs/All/...","company_name":"White Lodging"}'
```

Response:

```json
{
  "jobs": [{"title": "Director of Finance", "company_name": "White Lodging", "url": "...", "location": "Austin, TX"}],
  "company_name": "White Lodging",
  "url": "...",
  "method": "playwright:paylocity",
  "jobs_count": 12,
  "elapsed_ms": 4500,
  "error": null
}
```

### `GET /api/intelligence/companies`

List all companies with enriched intelligence (paginated, max 500/page).

```bash
curl https://scraper.myrtle.cloud/api/intelligence/companies?page=1&limit=50 \
  -H "X-API-Key: <SCRAPER_API_KEY>"
```

### `GET /api/intelligence/companies/{name}`

Get intelligence for a specific company — detected tech systems + ops/finance signal bullets.

### `GET /api/intelligence/digest/daily`

Daily snapshot: companies with new jobs in the last 24h (`unenriched_companies_24h`, `new_roles_24h`) and companies with hiring surges (2× week-over-week in `hiring_surge`).

### `POST /api/intelligence/enrich/{job_id}`

Manually trigger enrichment for a single job. Supports `?force=true` to re-enrich already-processed jobs.

## Supported ATS platforms

| ATS | URL pattern | Strategy |
|---|---|---|
| Paylocity | `recruiting.paylocity.com/...` | Playwright DOM |
| iCIMS | `*.icims.com` | Playwright DOM |
| Workday | `*.myworkdayjobs.com/...` | Playwright DOM |
| Greenhouse | `boards.greenhouse.io/...` | Playwright DOM |
| Lever | `jobs.lever.co/...` | Playwright DOM |
| UKG / UltiPro | `recruiting.ultipro.com/...` | Playwright DOM |
| SmartRecruiters | `*.smartrecruiters.com/...` | Playwright DOM |
| Paycom | `*.paycomonline.net/...` | API capture (JWT) |
| (anything else) | — | Generic parser |

## Intelligence layer

Jobs are enriched automatically every 5 minutes (APScheduler, max 1 concurrent batch of 10).

**System detection** — regex with word-boundary matching against a 40-entry hospitality tech taxonomy (Toast, Opera, HotSchedules, NetSuite, R365, Paycom, etc.).

**Bullet extraction** — Claude Haiku (`claude-haiku-4-5-20251001`) extracts ops/finance signal phrases from job descriptions. Categories: Cost Control, Financial Reporting, Budgeting & Forecasting, Data & Analytics, Compliance & Audit, Vendor Management.

**Idempotency** — each job enriches at most once; up to 3 retries on transient API failure. `enrichment_attempts` tracks failure count only.

## Architecture

- **Shared engine**: browser lifecycle, retries, concurrency, and API surface
- **Site adapters**: one module per ATS family under `app/site_adapters/`
- **Intelligence module**: `app/intelligence/` — extractor, enricher, routes
- **SQLite persistence**: jobs, companies, systems, bullets, company rollups via `aiosqlite`
- **Auth**: API key (`X-API-Key`) or session cookie; all `/api/` routes gated by `AuthMiddleware`
- **Rate limiting**: `slowapi` on scrape endpoints

## Local development

```bash
pip install -r requirements.txt
playwright install chromium
SCRAPER_API_KEY=dev SITE_PASSWORD=dev ANTHROPIC_API_KEY=sk-ant-... uvicorn app.main:app --reload --port 3010
```

## Deployment

Source is rsync'd to VPS then rebuilt:

```bash
rsync -av app/ requirements.txt docker-compose.yml root@<VPS_IP>:/docker/craftable-scraper/
ssh root@<VPS_IP> "cd /docker/craftable-scraper && docker compose up --build -d"
```

Exposed via Traefik at `scraper.myrtle.cloud`.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `SCRAPER_API_KEY` | Yes | API key for `/api/` endpoints |
| `SITE_PASSWORD` | Yes | Web UI password |
| `ANTHROPIC_API_KEY` | Yes | Claude Haiku key for bullet extraction |
| `SCRAPER_DB_PATH` | No | SQLite path (default: `/data/scraper.db`) |
| `SCRAPE_INTERVAL_HOURS` | No | Re-scrape cadence in hours (default: 24, 0 = off) |
| `PAYCOM_DETAIL_LIMIT` | No | Max job details fetched per Paycom run (default: 50) |
| `PAYCOM_DETAIL_DELAY` | No | Delay between Paycom detail requests in seconds (default: 0.2) |
