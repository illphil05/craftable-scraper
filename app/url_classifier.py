from __future__ import annotations
import re
from urllib.parse import urlparse

_DETAIL_PATTERNS = [
    re.compile(r"/jobs?/\d{4,}"),
    re.compile(r"/job/[a-z0-9-]{8,}"),
    re.compile(r"/careers?/\d{3,}"),
    re.compile(r"/position/\d+"),
    re.compile(r"/opening/\d+"),
    re.compile(r"/apply/\d+"),
]

# These hosts use non-standard URL structures; classify by path depth instead.
_DETAIL_PAGE_HOSTS = {
    "www.hcareers.com",
    "hcareers.com",
    "www.hospitalityjobs.com",
    "hospitalityjobs.com",
}

_HOST_DETAIL_RE = re.compile(r"/job-details?/|/jobs?/\d{4,}|/jobs?/[^/]+/[^/]+")

# Maps job-board hosts to their canonical listing root path.
_JOB_BOARD_ROOTS: dict[str, str] = {
    "www.hcareers.com": "/jobs",
    "hcareers.com": "/jobs",
    "www.hospitalityjobs.com": "/jobs",
    "hospitalityjobs.com": "/jobs",
}


def is_detail_page(url: str) -> bool:
    """Return True if URL looks like a single job detail page, not a listing."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if host in _DETAIL_PAGE_HOSTS:
        return bool(_HOST_DETAIL_RE.search(path))
    return any(p.search(path) for p in _DETAIL_PATTERNS)


def derive_careers_root_url(url: str) -> str:
    """Return the listing root for a URL, stripping job-detail paths.

    For known job-board hosts (hcareers, hospitalityjobs), a detail-page URL
    like /jobs/4336093-finance-specialist-... becomes /jobs.
    For all other URLs, including ATS and company-owned pages, the URL is
    returned unchanged — they don't have a meaningful listing root to derive.
    """
    if not url:
        return url
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    host = parsed.netloc.lower()
    root_path = _JOB_BOARD_ROOTS.get(host)
    if root_path and _HOST_DETAIL_RE.search(parsed.path.lower()):
        return f"{parsed.scheme}://{parsed.netloc}{root_path}"
    return url
