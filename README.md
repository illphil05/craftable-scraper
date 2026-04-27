# Craftable Scraper Service

Standalone Python/FastAPI microservice that scrapes JS-rendered ATS careers pages using Playwright + Chromium and returns structured job listings via REST API.

The scraper now uses an auto-discovered site adapter layer so ATS families stay isolated from the shared browser engine, persistence, and signal-detection framework.

## Why

Craftable Outreach's bundled scraper (Alpine + Node.js) cannot run a headless browser. JS-rendered ATS platforms (Paylocity, iCIMS, Workday) return empty HTML to simple HTTP fetches. This service handles those pages.

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
  -H "X-API-Key: craftable-scraper-2026" \
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

## Supported ATS platforms

| ATS | URL pattern |
|---|---|
| Paylocity | `recruiting.paylocity.com/...` |
| iCIMS | `*.icims.com` |
| Workday | `*.myworkdayjobs.com/...` |
| Greenhouse | `boards.greenhouse.io/...` |
| Lever | `jobs.lever.co/...` |
| UKG / UltiPro | `recruiting.ultipro.com/...` |
| SmartRecruiters | `*.smartrecruiters.com/...` |
| (anything else) | Generic parser |

## Architecture highlights

- **Shared engine**: browser lifecycle, retries, concurrency, and API surface
- **Site adapters**: one module per ATS family under `app/site_adapters`
- **Normalized persistence**: enriched job fields, site-family metadata, and field/signal evidence trails in SQLite
- **Signal detection**: weighted evidence scoring backed by `app/data/tech-taxonomy.json`

## Local development

```bash
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload --port 3010
```

## Deployment

Builds via Docker on Hostinger VPS, exposed via Traefik at `scraper.myrtle.cloud`.

```bash
# On VPS
docker compose up -d --build
```
