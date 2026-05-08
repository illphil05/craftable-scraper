from __future__ import annotations
import json
import re

_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.S | re.I,
)


def _extract_location(node: dict) -> str:
    loc = node.get("jobLocation") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    addr = loc.get("address") or {}
    if isinstance(addr, str):
        return addr
    parts = [addr.get("addressLocality"), addr.get("addressRegion")]
    return ", ".join(p for p in parts if p)


def extract_job_from_detail_page(
    html: str,
    url: str,
    company_name: str | None,
) -> dict | None:
    """Try JSON-LD Schema.org JobPosting extraction. Returns None if not found."""
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
