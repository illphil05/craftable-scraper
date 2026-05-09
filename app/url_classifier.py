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

# Single source of truth for job-board hosts.
# Keys are used for detail-page classification; values are the canonical listing root.
# Adding a new board here covers both is_detail_page() and derive_careers_root_url().
_JOB_BOARDS: dict[str, str] = {
    "www.hcareers.com": "/jobs",
    "hcareers.com": "/jobs",
    "www.hospitalityjobs.com": "/jobs",
    "hospitalityjobs.com": "/jobs",
}

_HOST_DETAIL_RE = re.compile(r"/job-details?/|/jobs?/\d{4,}|/jobs?/[^/]+/[^/]+")


def is_detail_page(url: str) -> bool:
    """Return True if URL looks like a single job detail page, not a listing."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if host in _JOB_BOARDS:
        return bool(_HOST_DETAIL_RE.search(path))
    return any(p.search(path) for p in _DETAIL_PATTERNS)


def derive_careers_root_url(url: str) -> str:
    """Strip a job-board detail path to its listing root, or return url unchanged."""
    if not url:
        return url
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    host = parsed.netloc.lower()
    root_path = _JOB_BOARDS.get(host)
    if root_path and _HOST_DETAIL_RE.search(parsed.path.lower()):
        return f"{parsed.scheme}://{parsed.netloc}{root_path}"
    return url
