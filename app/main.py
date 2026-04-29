"""Craftable Scraper Service — FastAPI app.

Endpoints:
  GET  /         - HTML UI (login or scraper) gated by SITE_PASSWORD cookie
  POST /login    - validate password, set session cookie
  POST /logout   - clear session cookie
  GET  /health   - liveness check
  GET  /api      - JSON service info
  POST /scrape   - scrape a careers page (X-API-Key header OR session cookie)
"""
import ipaddress
import os
import secrets
import socket
import time
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.db import init_db, close_db
from app.intelligence.intelligence_routes import router as intelligence_router
from app.logging_config import get_logger, make_request_id, setup_logging
from app.routes import router as api_router
from app.scheduler import start_scheduler, stop_scheduler
from app.scraper import scrape_url

setup_logging()
log = get_logger("main")

# ── Template setup ────────────────────────────────────────────────────────────
_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

# ── Auth configuration ────────────────────────────────────────────────────────
# Fail fast if critical secrets are absent from the environment (#1).
_API_KEY_RAW = os.environ.get("SCRAPER_API_KEY")
_SITE_PW_RAW = os.environ.get("SITE_PASSWORD")

if not _API_KEY_RAW:
    log.warning(
        "SCRAPER_API_KEY not set — generating a random key for this session. "
        "Set SCRAPER_API_KEY in the environment for a stable key."
    )
    _API_KEY_RAW = secrets.token_hex(32)

if not _SITE_PW_RAW:
    log.warning(
        "SITE_PASSWORD not set — generating a random password for this session. "
        "Set SITE_PASSWORD in the environment."
    )
    _SITE_PW_RAW = secrets.token_urlsafe(24)

API_KEY: str = _API_KEY_RAW
SITE_PASSWORD: str = _SITE_PW_RAW
SESSION_COOKIE = "scraper_session"
# A random, server-side-only session token — not derived from the password,
# so even knowledge of SITE_PASSWORD cannot forge a session cookie.
SESSION_VALUE = secrets.token_hex(64)

# ── Rate limiter (#3) ─────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    log.info("Craftable Scraper started")
    yield
    stop_scheduler()
    await close_db()
    log.info("Craftable Scraper shut down")


app = FastAPI(title="Craftable Scraper Service", version="1.2.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(api_router)
app.include_router(intelligence_router, prefix="/api")


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _is_authed(request: Request) -> bool:
    return request.cookies.get(SESSION_COOKIE) == SESSION_VALUE


def _require_auth(request: Request, x_api_key: str) -> None:
    if x_api_key and x_api_key == API_KEY:
        return
    if _is_authed(request):
        return
    raise HTTPException(status_code=401, detail="Unauthorized")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            api_key = request.headers.get("x-api-key", "")
            if not (api_key == API_KEY or _is_authed(request)):
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)


app.add_middleware(AuthMiddleware)


# ── SSRF protection (#12) ─────────────────────────────────────────────────────
_RFC1918_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / AWS metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_ssrf_url(url: str) -> bool:
    """Return True if *url* resolves to a private/loopback address."""
    try:
        from urllib.parse import urlparse
        hostname = urlparse(url).hostname
        if not hostname:
            return True
        addrs = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addrs:
            ip = ipaddress.ip_address(sockaddr[0])
            if any(ip in net for net in _RFC1918_NETWORKS):
                return True
        return False
    except Exception:
        # If we can't resolve, block it to be safe.
        return True


# ── Request/Response models ───────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    url: str
    company_name: str | None = None
    timeout: int = 30000
    debug: bool = False
    deep: bool = False


class JobResult(BaseModel):
    title: str
    company_name: str
    location: str | None = None
    url: str | None = None
    snippet: str | None = None
    department: str | None = None
    description: str | None = None
    requirements: list[str] | None = None
    full_address: str | None = None
    maps_url: str | None = None
    posted_date: str | None = None


class ScrapeResponse(BaseModel):
    jobs: list[JobResult]
    company_name: str
    url: str
    method: str
    adapter_family: str | None = None
    adapter_variant: str | None = None
    jobs_count: int
    elapsed_ms: int
    error: str | None = None
    html_sample: str | None = None
    html_size: int | None = None
    artifact_refs: dict | None = None


# ── UI endpoints ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, error: int = 0):
    if _is_authed(request):
        return templates.TemplateResponse("scraper.html", {"request": request})
    return templates.TemplateResponse("login.html", {"request": request, "error": bool(error)})


@app.post("/login")
async def login(password: str = Form(...)):
    if password != SITE_PASSWORD:
        return RedirectResponse(url="/?error=1", status_code=303)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE, SESSION_VALUE,
        httponly=True, secure=True, samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return response


@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


# ── Service endpoints ─────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "craftable-scraper", "version": "1.2.0"}


@app.get("/api")
async def api_info():
    return {"service": "craftable-scraper", "endpoints": ["/health", "/scrape", "/docs"]}


@app.post("/scrape", response_model=ScrapeResponse)
@limiter.limit("10/minute")
async def scrape(request: Request, x_api_key: str = Header(default=""), req: ScrapeRequest = Body(...)):
    _require_auth(request, x_api_key)

    if not req.url or not req.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")

    if len(req.url) > 2048:
        raise HTTPException(status_code=400, detail="URL too long")

    if req.company_name and len(req.company_name) > 200:
        raise HTTPException(status_code=400, detail="company_name too long")

    if _is_ssrf_url(req.url):
        raise HTTPException(status_code=400, detail="URL resolves to a private or disallowed address")

    request_id = make_request_id()
    log.info("Scrape request: url='%s' company='%s' [%s]", req.url, req.company_name, request_id)

    start = time.time()
    result = await scrape_url(
        req.url, req.company_name, req.timeout,
        debug=req.debug, deep=req.deep, request_id=request_id,
    )
    elapsed = int((time.time() - start) * 1000)

    log.info(
        "Scrape done: %d jobs, method=%s, elapsed=%dms [%s]",
        result["jobs_count"], result["method"], elapsed, request_id,
    )

    return ScrapeResponse(
        jobs=[JobResult(**j) for j in result["jobs"]],
        company_name=result["company_name"],
        url=result["url"],
        method=result["method"],
        adapter_family=result.get("adapter_family"),
        adapter_variant=result.get("adapter_variant"),
        jobs_count=result["jobs_count"],
        elapsed_ms=elapsed,
        error=result.get("error"),
        html_sample=result.get("html_sample"),
        html_size=result.get("html_size"),
        artifact_refs={
            "captured_response_urls": result.get("captured_response_urls", []),
            "captured_response_count": result.get("captured_response_count", 0),
        },
    )
