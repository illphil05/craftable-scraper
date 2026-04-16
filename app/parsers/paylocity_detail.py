"""Paylocity detail-page parser (Tier 2 deep scrape).

Parses a single /Recruiting/Jobs/Details/{jobId} page to extract
enrichment fields: description, requirements, full_address, maps_url, posted_date.

Uses the JSON-LD structured data block as the primary source, with
HTML fallbacks for fields missing from JSON-LD.
"""
import html as html_mod
import json
import re


def parse_detail(html: str) -> dict:
    """Parse a Paylocity /Details/{jobId} page. Returns enrichment dict.
    Keys: description, requirements (list), full_address, maps_url, posted_date.
    All keys are optional — return None for missing fields.
    """
    result = {
        "description": None,
        "requirements": None,
        "full_address": None,
        "maps_url": None,
        "posted_date": None,
    }

    jsonld = _extract_jsonld(html)

    # --- description ---
    result["description"] = _get_description(html, jsonld)

    # --- requirements ---
    result["requirements"] = _get_requirements(html)

    # --- maps_url ---
    result["maps_url"] = _get_maps_url(html)

    # --- full_address ---
    result["full_address"] = _get_full_address(html, jsonld)

    # --- posted_date ---
    result["posted_date"] = _get_posted_date(html, jsonld)

    return result


def _strip_html(text: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = html_mod.unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_jsonld(html: str) -> dict | None:
    m = re.search(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return None


def _get_description(html: str, jsonld: dict | None) -> str | None:
    # Try HTML first — the Description section content is cleaner
    m = re.search(
        r'<div[^>]*class="job-listing-header"[^>]*>Description</div>\s*<div[^>]*>(.*?)</div>\s*(?:<div[^>]*class="job-listing-header"|</div>)',
        html, re.DOTALL | re.IGNORECASE,
    )
    if m:
        text = _strip_html(m.group(1))
        if len(text) > 20:
            return text

    # Fallback to JSON-LD
    if jsonld and jsonld.get("description"):
        return _strip_html(jsonld["description"])

    return None


def _get_requirements(html: str) -> list[str] | None:
    # Look for the Requirements section in the HTML
    m = re.search(
        r'<div[^>]*class="job-listing-header"[^>]*>Requirements</div>\s*<div[^>]*>(.*?)</div>\s*(?:</div>|<div)',
        html, re.DOTALL | re.IGNORECASE,
    )
    if not m:
        # Also try data-bind="html: Job.Requirements"
        m = re.search(
            r'data-bind="html:\s*Job\.Requirements"[^>]*>(.*?)</div>',
            html, re.DOTALL | re.IGNORECASE,
        )
    if not m:
        return None

    items = re.findall(r'<li[^>]*>(.*?)</li>', m.group(1), re.DOTALL | re.IGNORECASE)
    if not items:
        return None

    cleaned = []
    for item in items:
        text = _strip_html(item).strip()
        if text:
            cleaned.append(text)
    return cleaned if cleaned else None


def _get_maps_url(html: str) -> str | None:
    m = re.search(r'href="(https?://maps\.google\.com/maps\?[^"]+)"', html, re.IGNORECASE)
    if m:
        return html_mod.unescape(m.group(1))
    # Also catch http variant
    m = re.search(r'href="(http://maps\.google\.com/maps\?[^"]+)"', html, re.IGNORECASE)
    if m:
        return html_mod.unescape(m.group(1))
    return None


def _get_full_address(html: str, jsonld: dict | None) -> str | None:
    # Prefer JSON-LD structured address
    if jsonld:
        loc = jsonld.get("jobLocation")
        if isinstance(loc, dict):
            addr = loc.get("address", {})
            if isinstance(addr, dict):
                parts = [
                    addr.get("streetAddress", ""),
                    addr.get("addressLocality", ""),
                    addr.get("addressRegion", ""),
                    addr.get("postalCode", ""),
                    addr.get("addressCountry", ""),
                ]
                full = ", ".join(p for p in parts if p)
                if full:
                    return full

    # Fallback: extract from maps URL query param
    m = re.search(r'maps\.google\.com/maps\?q=([^"&]+)', html, re.IGNORECASE)
    if m:
        addr = html_mod.unescape(m.group(1)).replace('+', ' ')
        if addr:
            return addr
    return None


def _get_posted_date(html: str, jsonld: dict | None) -> str | None:
    if jsonld and jsonld.get("datePosted"):
        raw = jsonld["datePosted"]
        # Return just the date portion (YYYY-MM-DD)
        m = re.match(r'(\d{4}-\d{2}-\d{2})', raw)
        if m:
            return m.group(1)
        return raw
    return None
