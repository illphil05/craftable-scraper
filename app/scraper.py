"""Core scraper — uses Playwright to render JS, then passes HTML to ATS parsers."""
from playwright.async_api import async_playwright

from app.parsers import get_parser, get_parser_name
from app.parsers.paylocity_detail import parse_detail as parse_paylocity_detail

# ATS-specific selectors to wait for after page load
WAIT_SELECTORS = {
    "paylocity.com": [".job-listing-card", "a[href*='Details']", ".job-title"],
    "icims.com": [".iCIMS_JobsTable", "a[href*='job']"],
    "myworkday": ["[data-automation-id='jobTitle']", "a[data-automation-id]"],
    "workdayjobs": ["[data-automation-id='jobTitle']", "a[data-automation-id]"],
    "greenhouse.io": [".job-post", ".opening", "tr.job-post"],
    "lever.co": [".posting-title", ".posting"],
    "ultipro.com": ["div[data-automation='opportunity']", "a[data-automation='job-title']", "a[href*='OpportunityDetail']"],
    "smartrecruiters.com": ["li.opening-job", ".details-title", "a.link--block"],
}


def _selectors_for(url: str) -> list[str]:
    url_lower = url.lower()
    for pattern, selectors in WAIT_SELECTORS.items():
        if pattern in url_lower:
            return selectors
    return []


DEEP_SCRAPE_LIMIT = 50
DEEP_PAGE_TIMEOUT = 15000


async def scrape_url(url: str, company_name: str | None = None, timeout: int = 30000, debug: bool = False, deep: bool = False) -> dict:
    """Scrape a URL with Playwright and return parsed job listings."""
    parser = get_parser(url)
    parser_name = get_parser_name(url)
    is_ukg = "ultipro.com" in url.lower()

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu',
                      '--disable-blink-features=AutomationControlled']
            )
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                viewport={'width': 1366, 'height': 768},
            )
            page = await context.new_page()
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            # UKG: set up XHR response capture BEFORE navigation
            ukg_api_responses = []
            if is_ukg:
                async def capture_response(response):
                    try:
                        ct = response.headers.get("content-type", "")
                        if "json" in ct or "opportunity" in response.url.lower() or "search" in response.url.lower():
                            body = await response.text()
                            if body and len(body) > 50:
                                ukg_api_responses.append(body)
                    except Exception:
                        pass
                page.on("response", capture_response)

            # Go to URL — networkidle waits for no network for 500ms
            try:
                await page.goto(url, wait_until='networkidle', timeout=timeout)
            except Exception:
                await page.goto(url, wait_until='domcontentloaded', timeout=timeout)

            # Wait for any ATS-specific selector
            selectors = _selectors_for(url)
            for sel in selectors:
                try:
                    await page.wait_for_selector(sel, timeout=8000, state='attached')
                    break
                except Exception:
                    continue

            # Scroll to trigger lazy-loaded content
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)
                await page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass

            # Final settle wait
            await page.wait_for_timeout(2000)

            html = await page.content()

            # UKG: extract shadow DOM + append captured API responses
            if is_ukg:
                await page.wait_for_timeout(3000)
                try:
                    shadow_html = await page.evaluate("""() => {
                        const parts = [];
                        function walk(root) {
                            root.querySelectorAll('*').forEach(el => {
                                if (el.shadowRoot) {
                                    parts.push(el.shadowRoot.innerHTML);
                                    walk(el.shadowRoot);
                                }
                            });
                        }
                        walk(document);
                        return parts.join('\\n');
                    }""")
                    if shadow_html and len(shadow_html) > 100:
                        html = html + "\n" + shadow_html
                except Exception:
                    pass
                for resp in ukg_api_responses:
                    html = html + "\n" + resp

            jobs = parser(html, url, company_name)

            # --- Tier 2: deep scrape detail pages ---
            if deep and jobs and "paylocity.com" in url.lower():
                for job in jobs[:DEEP_SCRAPE_LIMIT]:
                    job_url = job.get("url")
                    if not job_url:
                        continue
                    try:
                        await page.goto(job_url, wait_until='domcontentloaded', timeout=DEEP_PAGE_TIMEOUT)
                        await page.wait_for_timeout(1500)
                        detail_html = await page.content()
                        enrichment = parse_paylocity_detail(detail_html)
                        for key in ("description", "requirements", "full_address", "maps_url", "posted_date"):
                            if enrichment.get(key) is not None:
                                job[key] = enrichment[key]
                    except Exception:
                        pass

            await browser.close()

        result = {
            "jobs": jobs,
            "company_name": jobs[0]["company_name"] if jobs and jobs[0].get("company_name") else (company_name or ""),
            "url": url,
            "method": f"playwright:{parser_name}",
            "jobs_count": len(jobs),
            "error": None,
        }
        if debug:
            result["html_sample"] = html[:60000]
            result["html_size"] = len(html)
        return result
    except Exception as e:
        return {
            "jobs": [],
            "company_name": company_name or "",
            "url": url,
            "method": f"playwright:{parser_name}",
            "jobs_count": 0,
            "error": str(e),
        }
