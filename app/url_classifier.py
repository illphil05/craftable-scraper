from __future__ import annotations
import re
from urllib.parse import urlparse

_DETAIL_PATTERNS = [
    re.compile(r"/jobs?/\d{4,}"),
    re.compile(r"/job/[a-z0-9-]{8,}"),
    re.compile(r"/careers?/\d+"),
    re.compile(r"/position/\d+"),
    re.compile(r"/opening/\d+"),
    re.compile(r"/apply/\d+"),
]

_DETAIL_PAGE_HOSTS = {
    "www.hcareers.com",
    "hcareers.com",
    "www.hospitalityjobs.com",
    "hospitalityjobs.com",
}

def is_detail_page(url: str) -> bool:
    """Return True if URL looks like a single job detail page, not a listing."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.netloc.lower() in _DETAIL_PAGE_HOSTS:
        return True
    path = parsed.path.lower()
    return any(p.search(path) for p in _DETAIL_PATTERNS)
