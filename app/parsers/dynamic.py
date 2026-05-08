"""Dynamic parser — deterministic heuristics with confidence scoring.

Parse order:
  1. JSON-LD JobPosting                      (confidence 0.95)
  2. Embedded app state JSON (__NEXT_DATA__,
     Nuxt state, hydration blobs)            (confidence 0.85)
  3. ATS-like API JSON in HTML body          (confidence 0.80)
  4. Repeated job-card DOM patterns          (confidence 0.70)
  5. Job-like anchors                        (confidence 0.50)

Jobs below 0.50 confidence are not returned unless the caller explicitly
requests debug output.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

from app.logging_config import get_logger

log = get_logger("parser.dynamic")

MIN_CONFIDENCE = 0.50


# ── Public entry point ────────────────────────────────────────────────────────

def parse_dynamic(
    html: str,
    url: str,
    company_name: str | None = None,
    *,
    min_confidence: float = MIN_CONFIDENCE,
) -> list[dict]:
    """Return jobs extracted from *html* using deterministic heuristics.

    Only jobs with source_confidence >= min_confidence are returned.
    """
    for extractor, method, confidence in _STRATEGY_CHAIN:
        jobs = extractor(html, url, company_name, confidence)
        if jobs:
            log.debug("dynamic parser: %s found %d jobs (conf=%.2f)", method, len(jobs), confidence)
            return [j for j in jobs if j.get("source_confidence", 0) >= min_confidence]

    return []


# ── Strategy 1: JSON-LD JobPosting ───────────────────────────────────────────

def _parse_json_ld(html: str, url: str, company_name: str | None, confidence: float) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    for raw in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.IGNORECASE | re.DOTALL,
    ):
        try:
            blob = json.loads(raw.group(1))
        except (json.JSONDecodeError, ValueError):
            continue

        postings = _collect_job_postings(blob)
        for posting in postings:
            job = _normalize_json_ld_posting(posting, url, company_name, confidence)
            if job and job["title"] not in seen:
                seen.add(job["title"])
                jobs.append(job)

    return jobs


def _collect_job_postings(blob) -> list[dict]:
    if isinstance(blob, list):
        out = []
        for item in blob:
            out.extend(_collect_job_postings(item))
        return out
    if not isinstance(blob, dict):
        return []
    type_val = blob.get("@type", "")
    if isinstance(type_val, str) and type_val == "JobPosting":
        return [blob]
    if isinstance(type_val, list) and "JobPosting" in type_val:
        return [blob]
    # Recurse into graph
    out = []
    for key in ("@graph", "itemListElement", "jobs"):
        val = blob.get(key)
        if isinstance(val, list):
            for item in val:
                out.extend(_collect_job_postings(item))
    return out


def _normalize_json_ld_posting(posting: dict, base_url: str, company_name: str | None, confidence: float) -> dict | None:
    title = posting.get("title") or posting.get("name", "")
    if not title or len(title) < 4:
        return None

    # Apply URL
    apply_url = None
    apply_block = posting.get("url") or posting.get("sameAs")
    if isinstance(apply_block, str):
        apply_url = apply_block
    if not apply_url:
        apply_action = posting.get("applyAction") or posting.get("apply_action")
        if isinstance(apply_action, dict):
            apply_url = apply_action.get("target") or apply_action.get("url")

    # Location
    location = None
    job_location = posting.get("jobLocation")
    if isinstance(job_location, dict):
        addr = job_location.get("address", {})
        if isinstance(addr, dict):
            parts = [addr.get("streetAddress"), addr.get("addressLocality"),
                     addr.get("addressRegion"), addr.get("addressCountry")]
            location = ", ".join(p for p in parts if p)
        elif isinstance(addr, str):
            location = addr
    elif isinstance(job_location, str):
        location = job_location

    # Description
    description = posting.get("description")

    # Hiring org
    hiring_org = posting.get("hiringOrganization")
    if isinstance(hiring_org, dict):
        company_name = company_name or hiring_org.get("name")

    return {
        "title": str(title).strip(),
        "company_name": company_name or "",
        "url": apply_url,
        "location": location,
        "snippet": None,
        "department": posting.get("occupationalCategory"),
        "description": description,
        "source_site_family": "dynamic",
        "source_site_variant": "json_ld",
        "source_confidence": confidence,
        "extraction_method": "dynamic:json_ld",
    }


# ── Strategy 2: Embedded app state JSON ──────────────────────────────────────

_STATE_PATTERNS = [
    # Next.js
    r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    # Nuxt.js
    r'window\.__NUXT__\s*=\s*(\{.*?\});',
    # Generic hydration blobs
    r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
    r'window\.__APP_STATE__\s*=\s*(\{.*?\});',
    r'window\.__STATE__\s*=\s*(\{.*?\});',
    r'__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*;',
]

_JOB_KEYS = {"title", "jobTitle", "job_title", "name", "position", "positionTitle"}
_URL_KEYS = {"url", "applyUrl", "apply_url", "jobUrl", "job_url", "link", "href", "detailUrl"}
_LOC_KEYS = {"location", "locationName", "city", "cityName", "officeLocation", "workCity"}
_DEPT_KEYS = {"department", "departmentName", "category", "jobFunction", "businessUnit"}


def _parse_embedded_state(html: str, url: str, company_name: str | None, confidence: float) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    for pattern in _STATE_PATTERNS:
        for raw in re.finditer(pattern, html, re.DOTALL | re.IGNORECASE):
            try:
                blob = json.loads(raw.group(1))
            except (json.JSONDecodeError, ValueError):
                continue
            found = _extract_jobs_from_blob(blob, url, company_name, confidence)
            for job in found:
                key = job["title"].lower()
                if key not in seen:
                    seen.add(key)
                    jobs.append(job)
            if jobs:
                return jobs

    return jobs


def _extract_jobs_from_blob(blob, base_url: str, company_name: str | None, confidence: float, _depth: int = 0) -> list[dict]:
    if _depth > 8:
        return []
    if isinstance(blob, list):
        results = []
        for item in blob:
            results.extend(_extract_jobs_from_blob(item, base_url, company_name, confidence, _depth + 1))
        return results
    if not isinstance(blob, dict):
        return []

    # Check if this dict looks like a job
    title = _pick(blob, _JOB_KEYS)
    if title and isinstance(title, str) and 4 <= len(title) <= 200:
        job_url = _pick(blob, _URL_KEYS)
        if isinstance(job_url, str) and not job_url.startswith("http"):
            job_url = urljoin(base_url, job_url)
        location = _pick(blob, _LOC_KEYS)
        department = _pick(blob, _DEPT_KEYS)
        return [{
            "title": title.strip(),
            "company_name": company_name or "",
            "url": job_url if isinstance(job_url, str) else None,
            "location": str(location).strip() if location else None,
            "snippet": None,
            "department": str(department).strip() if department else None,
            "description": None,
            "source_site_family": "dynamic",
            "source_site_variant": "embedded_state",
            "source_confidence": confidence,
            "extraction_method": "dynamic:embedded_state",
        }]

    # Recurse into children
    results = []
    for val in blob.values():
        if isinstance(val, (dict, list)):
            results.extend(_extract_jobs_from_blob(val, base_url, company_name, confidence, _depth + 1))
    return results


def _pick(d: dict, keys: set[str]):
    for k in keys:
        if k in d and d[k]:
            return d[k]
    return None


# ── Strategy 3: ATS-like API JSON captured in HTML ───────────────────────────

_API_JSON_PATTERNS = [
    r'"jobs"\s*:\s*(\[.*?\])',
    r'"postings"\s*:\s*(\[.*?\])',
    r'"requisitions"\s*:\s*(\[.*?\])',
    r'"openings"\s*:\s*(\[.*?\])',
    r'"positions"\s*:\s*(\[.*?\])',
    r'"jobList"\s*:\s*(\[.*?\])',
    r'"results"\s*:\s*(\[.*?\])',
]


def _parse_api_json(html: str, url: str, company_name: str | None, confidence: float) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    for pattern in _API_JSON_PATTERNS:
        for raw in re.finditer(pattern, html, re.DOTALL):
            try:
                items = json.loads(raw.group(1))
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(items, list) or len(items) == 0:
                continue
            found = _extract_jobs_from_blob(items, url, company_name, confidence)
            for job in found:
                job["source_site_variant"] = "api_json"
                job["extraction_method"] = "dynamic:api_json"
                key = job["title"].lower()
                if key not in seen:
                    seen.add(key)
                    jobs.append(job)
            if jobs:
                return jobs

    return jobs


# ── Strategy 4: Repeated job-card DOM patterns ────────────────────────────────

_CARD_PATTERNS = [
    # Generic job-card / opening / posting wrappers
    r'<(?:li|div|article)[^>]*class="[^"]*(?:job[-_]?(?:card|item|post|listing|opening|row|result)|opening|posting)[^"]*"[^>]*>(.*?)</(?:li|div|article)>',
]

_TITLE_IN_CARD = [
    r'<(?:h[1-6]|span|p)[^>]*class="[^"]*(?:title|name|position)[^"]*"[^>]*>(.*?)</(?:h[1-6]|span|p)>',
    r'<(?:h[1-6])[^>]*>(.*?)</h[1-6]>',
]
_LINK_IN_CARD = r'href="([^"]+)"'
_LOC_IN_CARD = r'<(?:span|p|div)[^>]*class="[^"]*(?:location|city|region)[^"]*"[^>]*>(.*?)</(?:span|p|div)>'


def _parse_job_cards(html: str, url: str, company_name: str | None, confidence: float) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    for card_pattern in _CARD_PATTERNS:
        cards = re.findall(card_pattern, html, re.IGNORECASE | re.DOTALL)
        if len(cards) < 2:
            continue
        for card_html in cards:
            title = _extract_text_from_patterns(card_html, _TITLE_IN_CARD)
            if not title or len(title) < 4 or len(title) > 200:
                continue
            link_match = re.search(_LINK_IN_CARD, card_html)
            job_url = None
            if link_match:
                href = link_match.group(1)
                job_url = href if href.startswith("http") else urljoin(url, href)
            loc_match = re.search(_LOC_IN_CARD, card_html, re.IGNORECASE | re.DOTALL)
            location = _strip_tags(loc_match.group(1)).strip() if loc_match else None
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            jobs.append({
                "title": title,
                "company_name": company_name or "",
                "url": job_url,
                "location": location or None,
                "snippet": None,
                "department": None,
                "description": None,
                "source_site_family": "dynamic",
                "source_site_variant": "job_cards",
                "source_confidence": confidence,
                "extraction_method": "dynamic:job_cards",
            })
        if jobs:
            return jobs

    return jobs


def _extract_text_from_patterns(html: str, patterns: list[str]) -> str | None:
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE | re.DOTALL)
        if m:
            text = _strip_tags(m.group(1)).strip()
            if text and 4 <= len(text) <= 200:
                return text
    return None


def _strip_tags(html_frag: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', html_frag)
    text = re.sub(r'\s+', ' ', text)
    return text.replace('&amp;', '&').replace('&#39;', "'").replace('&nbsp;', ' ').strip()


# ── Strategy 5: Job-like anchors ──────────────────────────────────────────────

_JOB_ANCHOR_PATTERN = re.compile(
    r'<a[^>]*href="((?:https?://[^"]*)?(?:/[^"]*)?(?:job|career|position|opening|vacancy|requisition|apply)[^"]*)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)

_SKIP_ANCHOR_TEXT = {"jobs", "careers", "apply", "see all", "view all", "all jobs", "all positions", "learn more"}


def _parse_job_anchors(html: str, url: str, company_name: str | None, confidence: float) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    parsed_base = urlparse(url)

    for match in _JOB_ANCHOR_PATTERN.finditer(html):
        href = match.group(1)
        text = _strip_tags(match.group(2)).strip()
        if not text or len(text) < 4 or len(text) > 200:
            continue
        if text.lower() in _SKIP_ANCHOR_TEXT:
            continue
        if href.startswith("/"):
            href = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
        if not href.startswith("http"):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        jobs.append({
            "title": text,
            "company_name": company_name or "",
            "url": href,
            "location": None,
            "snippet": None,
            "department": None,
            "description": None,
            "source_site_family": "dynamic",
            "source_site_variant": "job_anchors",
            "source_confidence": confidence,
            "extraction_method": "dynamic:job_anchors",
        })

    return jobs


# ── Strategy chain ────────────────────────────────────────────────────────────

_STRATEGY_CHAIN = [
    (_parse_json_ld,        "json_ld",       0.95),
    (_parse_embedded_state, "embedded_state", 0.85),
    (_parse_api_json,       "api_json",       0.80),
    (_parse_job_cards,      "job_cards",      0.70),
    (_parse_job_anchors,    "job_anchors",    0.50),
]
