# Craftable Scraper — Rich Dashboard with Persistence

**Date:** 2026-04-17
**Status:** Approved
**Approach:** Option C — scraper gets its own SQLite DB for company tracking, job history, and tech stack detection. Outreach pipeline stays in craftable-outreach.

## Architecture

Add a SQLite database at `/opt/craftable-scraper/data/scraper.db` (host-mounted via docker-compose volume) with tables for companies, jobs, scrape history, and tech systems. The existing stateless `/scrape` endpoint continues working as-is for backward compatibility with craftable-outreach, but now also saves results to DB when a company is linked. The dashboard becomes a multi-page Alpine.js SPA (same inline HTML pattern, no build step) replacing the current simple scrape form.

Single `ui.py` file for the dashboard (~2000 lines). Matches the outreach pattern (`dashboard.html` is 40KB+). No build step, no npm, pure CDN dependencies.

## Database Schema

### `companies`
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PRIMARY KEY | UUID |
| name | TEXT NOT NULL | |
| slug | TEXT UNIQUE | lowercase-hyphenated, derived from name |
| website_url | TEXT | Company homepage |
| careers_url | TEXT | The ATS careers page URL |
| parent_company_name | TEXT | Free-text parent company reference |
| region | TEXT | Geographic region |
| notes_text | TEXT | Quick notes field |
| first_seen | TEXT | ISO timestamp |
| last_seen | TEXT | ISO timestamp, updated on each scrape |
| created_at | TEXT | ISO timestamp |

### `scrape_history`
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PRIMARY KEY | UUID |
| company_id | TEXT | FK to companies (nullable for ad-hoc scrapes) |
| url | TEXT NOT NULL | URL that was scraped |
| parser_used | TEXT | e.g. "playwright:paylocity" |
| jobs_found | INTEGER | Count |
| elapsed_ms | INTEGER | |
| error | TEXT | Null on success |
| html_size | INTEGER | |
| deep | BOOLEAN | Whether deep scrape was used |
| created_at | TEXT | ISO timestamp |

### `jobs`
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PRIMARY KEY | UUID |
| company_id | TEXT | FK to companies |
| scrape_id | TEXT | FK to scrape_history (the scrape that found/last-confirmed this job) |
| title | TEXT NOT NULL | |
| url | TEXT | Job posting URL |
| location | TEXT | |
| department | TEXT | |
| snippet | TEXT | Short description from listing |
| description | TEXT | Full description (from deep scrape) |
| requirements | TEXT | JSON array of requirement strings |
| full_address | TEXT | |
| maps_url | TEXT | |
| posted_date | TEXT | |
| first_seen | TEXT | ISO timestamp |
| last_seen | TEXT | ISO timestamp |
| is_active | BOOLEAN DEFAULT 1 | Set to 0 when job disappears from re-scrape |

### `company_systems`
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PRIMARY KEY | UUID |
| company_id | TEXT NOT NULL | FK to companies |
| system_name | TEXT | e.g. "Toast POS" |
| system_id | TEXT | e.g. "toast" |
| category | TEXT | e.g. "POS", "PMS", "Accounting" |
| confidence | REAL | 0.0-1.0 |
| matched_keywords | TEXT | JSON array of matched keywords |
| source | TEXT | "careers_page" or "job_description" |
| detected_at | TEXT | ISO timestamp |

### `company_notes`
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PRIMARY KEY | UUID |
| company_id | TEXT NOT NULL | FK to companies |
| note | TEXT NOT NULL | |
| created_at | TEXT | ISO timestamp |

## Tech Stack Detection

Port `tech-taxonomy.json` from craftable-outreach (`src/data/tech-taxonomy.json`). Contains 37 systems across 12 categories (POS, PMS, Accounting, ERP, Inventory, Procurement, Scheduling, Reservations, Payroll, Analytics, Delivery, Manual).

**Detection flow:** On each scrape, scan the full HTML + all job descriptions (if deep scrape) for taxonomy keywords. Each system has a list of keywords. Confidence = (distinct keywords matched / total keywords for that system). Store matches in `company_systems`. On re-scrape, delete old detections for that company and re-detect (idempotent).

**File:** `app/tech_detect.py` — loads taxonomy JSON, exposes `detect_systems(html: str, jobs: list[dict]) -> list[dict]`.

## Dashboard Pages (5 views)

### 1. Overview (`#/overview`)
- **Stat cards:** Companies, Total Jobs, Active Jobs, Systems Detected, Recent Scrapes (24h), Parsers Available
- **Search bar** + region filter dropdown
- **Companies table:** Name (clickable), Region, Jobs (active/total), Systems, Last Scraped, Actions (re-scrape button)
- Click company name → company detail page

### 2. Company Detail (`#/company/:id`)
- **Header card:** Name, website URL (link), careers URL (link), parent company, region, first/last seen timestamps
- **4 tabs:**
  1. **Jobs** — table of jobs (active highlighted, inactive grayed). Columns: Title, Location, Department, Posted Date, Status. Click row → slide-over with full description + requirements + address + maps link.
  2. **Tech Stack** — detected systems list with: system name, category badge, confidence bar (0-100%), matched keywords as tags, detection source.
  3. **Scrape History** — table of past scrapes: date, parser, jobs found, elapsed time, deep flag, error. Re-scrape button.
  4. **Notes** — chronological notes list with add-note form.
- **Edit company** button — modal to update name, website, careers URL, parent company, region.

### 3. Job Listings (`#/jobs`)
- All jobs across all companies
- Searchable by title, company name
- Filterable by: company (dropdown), department, location, active/inactive
- Table columns: Title, Company, Location, Department, Posted Date, Active status
- Click row → slide-over with full job details

### 4. Intelligence (`#/intelligence`)
- **Tech stack heatmap** — grid with systems as rows, companies as columns. Cell shows presence (colored) or absence (empty). Click system row to filter. Click company column to navigate to detail.
- **Hiring trends** — companies sorted by job count change since last scrape. Indicators: growing (green up arrow), shrinking (red down arrow), stable (gray dash).
- **Top departments** — aggregated department counts across all companies.

### 5. Scrape (`#/scrape`)
- Current scrape form moved here: URL, company name, timeout, deep, debug checkboxes
- Results shown inline (same as current UI)
- After scrape completes: "Save to Company" button. If company exists (matched by careers URL), auto-links. If new, creates company record.
- Recent scrapes list (from DB, not localStorage)

## API Endpoints

### Company CRUD
```
GET    /api/companies              — list with search, region filter, pagination
GET    /api/companies/:id          — detail with systems, recent jobs, scrape count
POST   /api/companies              — create {name, website_url, careers_url, parent_company_name, region}
PUT    /api/companies/:id          — update fields
DELETE /api/companies/:id          — soft delete (or hard delete if no scrape history)
```

### Jobs
```
GET    /api/jobs                   — all jobs, filterable by company_id, department, location, is_active, search
GET    /api/jobs/:id               — single job with full description
```

### Company sub-resources
```
GET    /api/companies/:id/jobs     — jobs for this company
GET    /api/companies/:id/scrapes  — scrape history
GET    /api/companies/:id/systems  — detected tech systems
POST   /api/companies/:id/notes    — add note {note: string}
DELETE /api/companies/:id/notes/:nid — delete note
```

### Dashboard data
```
GET    /api/stats                  — overview stat counts
GET    /api/systems-heatmap        — {systems: [...], companies: [...], matrix: [[...]]}
```

### Existing (unchanged)
```
POST   /scrape                     — existing endpoint, backward compatible
GET    /health                     — liveness
GET    /api                        — service info
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/db.py` | NEW | SQLite connection, schema creation, CRUD helpers |
| `app/tech_detect.py` | NEW | Taxonomy loader + HTML keyword scanner |
| `app/data/tech-taxonomy.json` | NEW | Copied from outreach, 37 systems |
| `app/routes.py` | NEW | All new API route handlers (keeps main.py clean) |
| `app/main.py` | MODIFY | Import routes, init DB on startup, wire scrape→save |
| `app/ui.py` | REWRITE | Full SPA dashboard replacing current simple UI |
| `app/scraper.py` | NO CHANGE | Stateless scraper stays as-is |
| `docker-compose.yml` | MODIFY | Add host volume mount for /data |
| `requirements.txt` | NO CHANGE | SQLite is stdlib, no new deps |

## Integration with craftable-outreach

The existing `POST /scrape` endpoint contract is **unchanged**. craftable-outreach continues calling it with `X-API-Key` header. The scraper optionally saves results to its own DB (when company is linked via the UI), but the API response is identical.

## Persistence Strategy

- Host directory: `/opt/craftable-scraper/data/` on VPS
- Docker volume mount: `./data:/data` in docker-compose.yml won't work with delete+recreate pattern
- Instead: absolute host mount `/opt/craftable-scraper/data:/data`
- One-time setup: `mkdir -p /opt/craftable-scraper/data` on VPS
- DB path in app: `/data/scraper.db` (inside container)
- Schema auto-created on first startup via `db.init_db()`

## Constraints

- No build step. Pure HTML + Tailwind CDN + Alpine.js CDN.
- Light mode UI (user preference).
- Python only, no Node.js dependencies.
- SQLite only, no Postgres.
- Must not break existing `/scrape` API contract.
- Host volume must survive deploy cycles (delete+recreate project).
