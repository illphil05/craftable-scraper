"""Tech stack detection — scans HTML for hospitality system keywords."""
import json
import os

from bs4 import BeautifulSoup

_taxonomy: list[dict] | None = None
TAXONOMY_PATH = os.path.join(os.path.dirname(__file__), "data", "tech-taxonomy.json")


def _load_taxonomy() -> list[dict]:
    global _taxonomy
    if _taxonomy is None:
        with open(TAXONOMY_PATH) as f:
            data = json.load(f)
        _taxonomy = data["systems"]
    return _taxonomy


def detect_systems(html: str, jobs: list[dict] | None = None) -> list[dict]:
    """Scan HTML and job descriptions for tech system keywords.

    Returns list of dicts with: system_id, system_name, category, confidence, matched_keywords, source
    """
    taxonomy = _load_taxonomy()

    # Build combined text corpus
    careers_text = _strip_tags(html).lower()
    job_texts = []
    if jobs:
        for j in jobs:
            parts = [j.get("title", ""), j.get("description", ""), j.get("snippet", "")]
            if isinstance(j.get("requirements"), list):
                parts.extend(j["requirements"])
            elif isinstance(j.get("requirements"), str):
                parts.append(j["requirements"])
            job_texts.append(" ".join(p for p in parts if p).lower())
    all_job_text = " ".join(job_texts)

    detections = []
    for system in taxonomy:
        keywords = system.get("keywords", [])
        if not keywords:
            continue

        matched = []
        source = None
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in careers_text:
                matched.append(kw)
                source = source or "careers_page"
            if kw_lower in all_job_text:
                matched.append(kw)
                source = source or "job_description"

        matched = list(set(matched))
        if not matched:
            continue

        confidence = min(1.0, len(matched) / max(len(keywords), 1))
        detections.append({
            "system_id": system["system_id"],
            "system_name": system["system_name"],
            "category": system["category"],
            "confidence": round(confidence, 2),
            "matched_keywords": matched,
            "source": source,
        })

    detections.sort(key=lambda d: d["confidence"], reverse=True)
    return detections


def _strip_tags(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(separator=" ")
