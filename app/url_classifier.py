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

_HOST_DETAIL_RE = re.compile(r"/job-details?/|/jobs?/[^/]+/[^/]+")


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
