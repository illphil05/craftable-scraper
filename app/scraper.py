"""Core scraper — uses Playwright to render JS, then passes HTML to ATS parsers."""
from playwright.async_api import async_playwright

from app.parsers import get_parser, get_parser_name


async def scrape_url(url: str, company_name: str | None = None, timeout: int = 30000) -> dict:
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

            # Extra wait for SPA frameworks to render (Angular/React/Vue)
            await page.wait_for_timeout(3000)

            html = await page.content()
            await browser.close()

        jobs = parser(html, url, company_name)

        return {
            "jobs": jobs,
            "company_name": jobs[0]["company_name"] if jobs and jobs[0].get("company_name") else (company_name or ""),
            "url": url,
            "method": f"playwright:{parser_name}",
            "jobs_count": len(jobs),
            "error": None,
        }
    except Exception as e:
        return {
            "jobs": [],
            "company_name": company_name or "",
            "url": url,
            "method": f"playwright:{parser_name}",
            "jobs_count": 0,
            "error": str(e),
        }
