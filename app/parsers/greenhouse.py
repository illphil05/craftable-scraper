"""Greenhouse ATS parser — rewrote HTML parsing with BeautifulSoup.

URL pattern: boards.greenhouse.io/{company} or boards.greenhouse.io/embed/job_board?for={company}

Modern Greenhouse uses React with classes like:
  - tr.job-post / div.job-post (each job row)
  - div.opening (legacy)
  - a[href*='/jobs/'] (job detail links)
"""
from urllib.parse import urljoin
import re

from bs4 import BeautifulSoup

from app.parsers import register_parser

_BADGE_TEXTS = {"new", "featured", "recently posted", "apply", "remote"}


@register_parser("greenhouse.io", [".job-post", ".opening", "tr.job-post"])
def parse(html: str, url: str, company_name: str | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")

    # ── Strategy 1: Modern Greenhouse job-post rows ──────────────────────────
    for row in soup.find_all(["tr", "div"], class_=lambda c: c and "job-post" in c.split()):
        link = row.find("a", href=True)
        if not link:
            continue
        href = link["href"]

        # Title: prefer a child element with a recognised class, fall back to
        # the first <p> or heading, then the full link text.
        title = None
        for cls in ("body--medium", "title", "name", "posting-name"):
            el = link.find(class_=lambda c, _cls=cls: c and _cls in c.split())
            if el:
                candidate = el.get_text(strip=True)
                if candidate and len(candidate) > 3 and candidate.lower() not in _BADGE_TEXTS:
                    title = candidate
                    break
        if not title:
            for tag in ("p", "h2", "h3", "h4", "h5"):
                el = link.find(tag)
                if el:
                    candidate = el.get_text(strip=True)
                    if candidate and len(candidate) > 3 and candidate.lower() not in _BADGE_TEXTS:
                        title = candidate
                        break
        if not title:
            title = _clean_text(link)

        # Location
        location = None
        loc_el = row.find(class_=lambda c: c and any(
            x in c.split() for x in ("location", "body__secondary", "secondary", "location-tag")
        ))
        if loc_el:
            location = loc_el.get_text(strip=True) or None

        _add(jobs, seen, title, href, url, company_name, location=location)

    if jobs:
        return jobs

    # ── Strategy 2: Legacy .opening divs ────────────────────────────────────
    for div in soup.find_all("div", class_=lambda c: c and "opening" in c.split()):
        link = div.find("a", href=True)
        if not link:
            continue
        href = link["href"]
        title = _clean_text(link)
        loc_el = div.find(class_=lambda c: c and "location" in (c.split() if c else []))
        location = loc_el.get_text(strip=True) if loc_el else None
        _add(jobs, seen, title, href, url, company_name, location=location)

    if jobs:
        return jobs

    # ── Strategy 3: Fallback — any anchor pointing at /jobs/{id} ────────────
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/jobs/" in href and any(c.isdigit() for c in href.split("/jobs/")[-1][:10]):
            _add(jobs, seen, _clean_text(link), href, url, company_name)

    return jobs


def _clean_text(tag) -> str:
    text = tag.get_text(separator=" ", strip=True)
    # Strip Greenhouse badge suffixes concatenated without spaces
    text = re.sub(r"(?<=[a-z0-9])(New|Featured|Recently Posted)$", "", text).strip()
    text = re.sub(r"\s+(New|Featured|Recently Posted)\s*$", "", text, flags=re.IGNORECASE).strip()
    return text


def _add(
    jobs: list,
    seen: set,
    title: str,
    href: str | None,
    base_url: str,
    company_name: str | None,
    location: str | None = None,
):
    if not title or len(title) < 4 or len(title) > 150:
        return
    key = title.lower()
    if key in seen:
        return
    seen.add(key)
    full_url = urljoin(base_url, href) if href and not href.startswith("http") else href
    jobs.append({
        "title": title,
        "company_name": company_name or "",
        "url": full_url,
        "location": location,
        "snippet": None,
        "department": None,
    })
