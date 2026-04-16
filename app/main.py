"""Craftable Scraper Service — FastAPI app.

Endpoints:
  GET  /         - HTML UI (login or scraper) gated by SITE_PASSWORD cookie
  POST /login    - validate password, set session cookie
  POST /logout   - clear session cookie
  GET  /health   - liveness check
  GET  /api      - JSON service info
  POST /scrape   - scrape a careers page (X-API-Key header OR session cookie)
"""
import hashlib
import os
import time

from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from app.scraper import scrape_url
from app.ui import login_page, scraper_page

app = FastAPI(title="Craftable Scraper Service", version="1.1.0")

API_KEY = os.environ.get("SCRAPER_API_KEY", "craftable-scraper-2026")
SITE_PASSWORD = os.environ.get("SITE_PASSWORD", "Miles2026")
SESSION_COOKIE = "scraper_session"
SESSION_VALUE = hashlib.sha256(f"{SITE_PASSWORD}:scraper-ui".encode()).hexdigest()


def _is_authed(request: Request) -> bool:
    return request.cookies.get(SESSION_COOKIE) == SESSION_VALUE


def _require_auth(request: Request, x_api_key: str) -> None:
    if x_api_key and x_api_key == API_KEY:
        return
    if _is_authed(request):
        return
    raise HTTPException(status_code=401, detail="Unauthorized")


class ScrapeRequest(BaseModel):
    url: str
    company_name: str | None = None
    timeout: int = 30000
    debug: bool = False


class JobResult(BaseModel):
    title: str
    company_name: str
    location: str | None = None
    url: str | None = None
    snippet: str | None = None
    department: str | None = None


class ScrapeResponse(BaseModel):
    jobs: list[JobResult]
    company_name: str
    url: str
    method: str
    jobs_count: int
    elapsed_ms: int
    error: str | None = None
    html_sample: str | None = None
    html_size: int | None = None


@app.get("/", response_class=HTMLResponse)
async def root(request: Request, error: int = 0):
    if _is_authed(request):
        return HTMLResponse(scraper_page())
    return HTMLResponse(login_page(error=bool(error)))


@app.post("/login")
async def login(password: str = Form(...)):
    if password != SITE_PASSWORD:
        return RedirectResponse(url="/?error=1", status_code=303)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE, SESSION_VALUE,
        httponly=True, secure=True, samesite="lax",
        max_age=60 * 60 * 24 * 30,  # 30 days
    )
    return response


@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/health")
async def health():
    return {"status": "ok", "service": "craftable-scraper", "version": "1.1.0"}


@app.get("/api")
async def api_info():
    return {"service": "craftable-scraper", "endpoints": ["/health", "/scrape", "/docs"]}


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape(req: ScrapeRequest, request: Request, x_api_key: str = Header(default="")):
    _require_auth(request, x_api_key)

    if not req.url or not req.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")

    start = time.time()
    result = await scrape_url(req.url, req.company_name, req.timeout, debug=req.debug)
    elapsed = int((time.time() - start) * 1000)

    return ScrapeResponse(
        jobs=[JobResult(**j) for j in result["jobs"]],
        company_name=result["company_name"],
        url=result["url"],
        method=result["method"],
        jobs_count=result["jobs_count"],
        elapsed_ms=elapsed,
        error=result["error"],
        html_sample=result.get("html_sample"),
        html_size=result.get("html_size"),
    )
