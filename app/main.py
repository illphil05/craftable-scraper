"""Craftable Scraper Service — FastAPI app.

Endpoints:
  GET  /health  - liveness check
  POST /scrape  - scrape a careers page (requires X-API-Key header)
"""
import os
import time

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.scraper import scrape_url

app = FastAPI(title="Craftable Scraper Service", version="1.0.0")

API_KEY = os.environ.get("SCRAPER_API_KEY", "craftable-scraper-2026")


class ScrapeRequest(BaseModel):
    url: str
    company_name: str | None = None
    timeout: int = 30000


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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "craftable-scraper", "version": "1.0.0"}


@app.get("/")
async def root():
    return {"service": "craftable-scraper", "endpoints": ["/health", "/scrape"]}


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape(req: ScrapeRequest, x_api_key: str = Header(default="")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not req.url or not req.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")

    start = time.time()
    result = await scrape_url(req.url, req.company_name, req.timeout)
    elapsed = int((time.time() - start) * 1000)

    return ScrapeResponse(
        jobs=[JobResult(**j) for j in result["jobs"]],
        company_name=result["company_name"],
        url=result["url"],
        method=result["method"],
        jobs_count=result["jobs_count"],
        elapsed_ms=elapsed,
        error=result["error"],
    )
