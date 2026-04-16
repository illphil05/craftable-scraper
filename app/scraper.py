"""Core scraper — uses Playwright to render JS, then passes HTML to ATS parsers."""
from playwright.async_api import async_playwright

from app.parsers import get_parser, get_parser_name

# ATS-specific selectors to wait for after page load
WAIT_SELECTORS = {
    "paylocity.com": [".job-listing-card", "a[href*='Details']", ".job-title"],
    "icims.com": [".iCIMS_JobsTable", "a[href*='job']"],
    "myworkday": ["[data-automation-id='jobTitle']", "a[data-automation-id]"],
    "workdayjobs": ["[data-automation-id='jobTitle']", "a[data-automation-id]"],
    "greenhouse.io": [".job-post", ".opening", "tr.job-post"],
    "lever.co": [".posting-title", ".posting"],
}


def _selectors_for(url: str) -> list[str]:
    url_lower = url.lower()
    for pattern, selectors in WAIT_SELECTORS.items():
        if pattern in url_lower:
            return selectors
    return []


async def scrape_url(url: str, company_name: str | None = None, timeout: int = 30000, debug: bool = False) -> dict:
    """Scrape a URL with Playwright and return parsed job listings.

    Args:
        url: The careers page URL to scrape
        company_name: Optional company name to attach to each job
        timeout: Page load timeout in milliseconds

    Returns:
        dict with keys: jobs, company_name, url, method, jobs_count, error
    """
    parser = get_parser(url)
    parser_name = get_parser_name(url)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1366, 'height': 768},
            )
            page = await context.new_page()

            # Go to URL — networkidle waits for no network for 500ms
            try:
                await page.goto(url, wait_until='networkidle', timeout=timeout)
            except Exception:
                # Fall back to domcontentloaded if networkidle times out
                await page.goto(url, wait_until='domcontentloaded', timeout=timeout)

            # Wait for any ATS-specific selector to appear (gives React/Angular time to render)
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
            await browser.close()

        jobs = parser(html, url, company_name)

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
