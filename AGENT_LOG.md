
## Agent C — Tailwind Build Infrastructure
- [OK] Created tailwind.config.js at project root (scans ./app/templates/**/*.html)
- [OK] Created app/static/input.css (new directory created automatically)
- [OK] Updated Dockerfile — inserted Tailwind build step after `COPY app/ ./app/` (also added `COPY tailwind.config.js .` so the config is available during build); step installs nodejs/npm, runs npx tailwindcss --minify, then purges node artefacts before EXPOSE/CMD
- [OK] Mounted /static in app/main.py — added StaticFiles mount after app.include_router calls; guarded with os.path.isdir check so it only mounts if the directory exists
- [OK] Updated .gitignore — added app/static/output.css, node_modules/, package-lock.json, package.json

## Agent B — Python Scraper Fixes
- [OK] Created app/url_classifier.py (is_detail_page with regex patterns + known host set)
- [OK] Created app/parsers/detail.py (extract_job_from_detail_page via JSON-LD schema.org)
- [OK] Added is_detail_page and extract_job_from_detail_page imports to scraper.py
- [OK] Added Strategy 0 detail page block in scrape_url() — before API-first step; uses _scrape_attempt with debug=True to capture html_sample for JSON-LD parsing; falls through to normal pipeline if no JSON-LD found
- [OK] Added _BASELINE_IGNORED_TITLES constant above _is_ignored_title()
- [OK] Merged baseline patterns with caller patterns: effective_ignored_patterns = _BASELINE_IGNORED_TITLES + (ignored_title_patterns or [])
- [NOTE] _scrape_attempt() actual signature requires deep, ignored_title_patterns, parser_name — Strategy 0 passes deep=False, ignored_title_patterns=[], parser_name=adapter.manifest.family. html_sample is captured by forcing debug=True on the detail page fetch (avoids a second Playwright fetch).

## Agent A — Template Fixes
- [OK] Fixed heatmap init (`heatmap: null` → `heatmap: { companies: [] }`)
- [OK] Swapped x-show→x-if on heatmap container (line ~455)
- [OK] Fixed companion empty-state: `x-show="!heatmap || heatmap.companies.length === 0"` → `x-show="heatmap.companies.length === 0"`
- [OK] Fixed scrapeResult x-if (line ~572): x-show→x-if
- [OK] Replaced Tailwind CDN `<script src="https://cdn.tailwindcss.com">` with `<link rel="stylesheet" href="/static/output.css">`
- [OK] Google Fonts preconnect tags already present; `&display=swap` already present — no changes needed
- [OK] Added id/name to 19 inputs/selects/textareas (companiesSearch, companiesRegion, editForm.name, editForm.website_url, editForm.careers_url, editForm.parent_company_name, editForm.region, newNote, jobsSearch, jobsCompany, jobsDept, scrapeUrl, scrapeCompany, scrapeTimeout, scrapeDeep, scrapeDebug, saveCompanyName, job.title loop, job.location loop)
- [OK] Added for to 8 labels (edit-name, edit-website-url, edit-careers-url, edit-parent, edit-region, scrape-url, scrape-company, scrape-timeout); checkbox labels left as-is (wrapping pattern)
