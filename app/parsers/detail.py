from __future__ import annotations
import json
import re

_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.S | re.I,
)
_OG_TAG_RE = re.compile(r'<meta\b[^>]+>', re.I)
_OG_PROP_RE = re.compile(r'property=["\']og:(\w+)["\']', re.I)
_OG_CONTENT_RE = re.compile(r'content=["\']([^"\']*)["\']', re.I)
_TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.S | re.I)

# "Job Title at Company Name in City, ST" — common hospitality job board pattern
_DESC_AT_RE = re.compile(r'^apply\s+now\s+for\s+(.+?)\s+at\s+(.+?)\s+in\s+(.+?)(?:\s*[—\-]|$)', re.I)
# "<title>Job Title at Company | SiteName</title>"
_TITLE_AT_RE = re.compile(r'^(.+?)\s+at\s+(.+?)\s*\|', re.I)


def _extract_location(node: dict) -> str:
    loc = node.get("jobLocation") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    addr = loc.get("address") or {}
    if isinstance(addr, str):
        return addr
    parts = [addr.get("addressLocality"), addr.get("addressRegion")]
    return ", ".join(p for p in parts if p)


def _try_jsonld(html: str, url: str, company_name: str | None) -> dict | None:
    for m in _JSONLD_RE.finditer(html):
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("@type") != "JobPosting":
                continue
            title = node.get("title") or node.get("name") or ""
            if not title:
                continue
            org = node.get("hiringOrganization") or {}
            detected_company = (
                org.get("name") if isinstance(org, dict) else None
            ) or company_name or ""
            return {
                "title": title.strip(),
                "company_name": detected_company,
                "location": _extract_location(node),
                "url": node.get("url") or url,
                "department": node.get("occupationalCategory") or "",
                "description": node.get("description") or "",
                "source_site_family": "jsonld",
                "source_site_variant": "detail_page",
                "source_confidence": 0.99,
            }
    return None


def _try_og_tags(html: str, url: str, company_name: str | None) -> dict | None:
    og: dict[str, str] = {}
    for tag in _OG_TAG_RE.finditer(html[:8_000]):
        pm = _OG_PROP_RE.search(tag.group())
        cm = _OG_CONTENT_RE.search(tag.group())
        if pm and cm:
            og[pm.group(1)] = cm.group(1)
    title = og.get("title", "").strip()
    if not title:
        return None

    description = og.get("description", "")
    location = ""
    detected_company = company_name or ""

    # Try to extract company + location from og:description
    m = _DESC_AT_RE.match(description)
    if m:
        detected_company = m.group(2).strip() or detected_company
        location = m.group(3).strip()

    # Fall back to <title> tag for company
    if not detected_company:
        t = _TITLE_RE.search(html[:4_000])
        if t:
            tm = _TITLE_AT_RE.match(t.group(1).strip())
            if tm:
                detected_company = tm.group(2).strip()

    return {
        "title": title,
        "company_name": detected_company,
        "location": location,
        "url": og.get("url") or url,
        "department": "",
        "description": description,
        "source_site_family": "og_meta",
        "source_site_variant": "detail_page",
        "source_confidence": 0.85,
    }


def extract_job_from_detail_page(
    html: str,
    url: str,
    company_name: str | None,
) -> dict | None:
    """Extract a single job from a detail page. Tries JSON-LD first, OG tags second."""
    if not html:
        return None
    return _try_jsonld(html, url, company_name) or _try_og_tags(html, url, company_name)
