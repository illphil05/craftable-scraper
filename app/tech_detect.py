"""Tech stack detection — weighted evidence-based system detection."""
from __future__ import annotations

import json
import os
from collections import Counter

from bs4 import BeautifulSoup

_taxonomy: list[dict] | None = None
_taxonomy_version: str | None = None
TAXONOMY_PATH = os.path.join(os.path.dirname(__file__), "data", "tech-taxonomy.json")


def _load_taxonomy() -> list[dict]:
    global _taxonomy, _taxonomy_version
    if _taxonomy is None:
        with open(TAXONOMY_PATH) as f:
            data = json.load(f)
        _taxonomy = data["systems"]
        _taxonomy_version = data.get("taxonomy_version", "1.0")
    return _taxonomy


def get_taxonomy_version() -> str:
    _load_taxonomy()
    return _taxonomy_version or "1.0"


def detect_systems(html: str, jobs: list[dict] | None = None) -> list[dict]:
    """Scan HTML and jobs for weighted system evidence."""
    taxonomy = _load_taxonomy()
    sources = _build_sources(html, jobs or [])
    detections = []

    for system in taxonomy:
        aliases = _unique(system.get("aliases") or system.get("keywords") or [])
        strong_signals = _unique(system.get("strong_signals") or aliases)
        weak_signals = _unique(system.get("weak_signals") or [])
        negative_signals = _unique(system.get("negative_signals") or [])
        related_roles = _unique(system.get("related_roles") or [])
        related_departments = _unique(system.get("related_departments") or [])
        weights = {
            "alias": 0.35,
            "strong": 0.45,
            "weak": 0.2,
            "role": 0.1,
            "department": 0.1,
            "negative": -0.4,
        }
        weights.update(system.get("confidence_weights") or {})

        score = 0.0
        matched_keywords: list[str] = []
        evidence: list[dict] = []
        source_counter: Counter[str] = Counter()

        for signal_type, phrases in (
            ("alias", aliases),
            ("strong", strong_signals),
            ("weak", weak_signals),
        ):
            for phrase in phrases:
                for source_name, matched_phrase in _match_signal(phrase, sources):
                    matched_keywords.append(phrase)
                    contribution = float(weights.get(signal_type, 0.0))
                    score += contribution
                    evidence.append(
                        {
                            "signal_type": signal_type,
                            "matched_phrase": matched_phrase,
                            "evidence_source": source_name,
                            "confidence_contribution": round(contribution, 2),
                            "exclusion_checks": [],
                        }
                    )
                    source_counter[source_name] += 1

        for phrase in related_roles:
            role_sources = {
                source_name: source_text
                for source_name, source_text in sources.items()
                if source_name in {"job_title", "job_description"}
            }
            for source_name, matched_phrase in _match_signal(phrase, role_sources):
                contribution = float(weights.get("role", 0.0))
                score += contribution
                evidence.append(
                    {
                        "signal_type": "related_role",
                        "matched_phrase": matched_phrase,
                        "evidence_source": source_name,
                        "confidence_contribution": round(contribution, 2),
                        "exclusion_checks": [],
                    }
                )
                source_counter[source_name] += 1

        for phrase in related_departments:
            for source_name, matched_phrase in _match_signal(phrase, {"job_department": sources.get("job_department", "")}):
                contribution = float(weights.get("department", 0.0))
                score += contribution
                evidence.append(
                    {
                        "signal_type": "related_department",
                        "matched_phrase": matched_phrase,
                        "evidence_source": source_name,
                        "confidence_contribution": round(contribution, 2),
                        "exclusion_checks": [],
                    }
                )
                source_counter[source_name] += 1

        exclusions: list[str] = []
        for phrase in negative_signals:
            for source_name, matched_phrase in _match_signal(phrase, sources):
                contribution = float(weights.get("negative", -0.4))
                score += contribution
                exclusions.append(f"{source_name}:{matched_phrase}")
                evidence.append(
                    {
                        "signal_type": "negative",
                        "matched_phrase": matched_phrase,
                        "evidence_source": source_name,
                        "confidence_contribution": round(contribution, 2),
                        "exclusion_checks": exclusions.copy(),
                    }
                )

        confidence = max(0.0, min(score, 1.0))
        matched_keywords = _unique(matched_keywords)
        if not matched_keywords or confidence <= 0:
            continue

        source = source_counter.most_common(1)[0][0] if source_counter else "careers_page"
        detections.append(
            {
                "system_id": system["system_id"],
                "system_name": system["system_name"],
                "category": system["category"],
                "confidence": round(confidence, 2),
                "matched_keywords": matched_keywords,
                "source": source,
                "evidence": evidence,
                "taxonomy_version": get_taxonomy_version(),
                "pain_points": system.get("pain_points", []),
                "craftable_angle": system.get("craftable_angle"),
            }
        )

    detections.sort(key=lambda d: d["confidence"], reverse=True)
    return detections


def _build_sources(html: str, jobs: list[dict]) -> dict[str, str]:
    careers_text = _strip_tags(html).lower()
    job_titles = []
    job_descriptions = []
    job_departments = []
    job_requirements = []
    for job in jobs:
        if job.get("title"):
            job_titles.append(str(job["title"]))
        if job.get("description"):
            job_descriptions.append(str(job["description"]))
        if job.get("snippet"):
            job_descriptions.append(str(job["snippet"]))
        if job.get("department"):
            job_departments.append(str(job["department"]))
        requirements = job.get("requirements")
        if isinstance(requirements, list):
            job_requirements.extend(str(item) for item in requirements)
        elif requirements:
            job_requirements.append(str(requirements))
    return {
        "careers_page": careers_text,
        "job_title": " ".join(job_titles).lower(),
        "job_description": " ".join(job_descriptions).lower(),
        "job_department": " ".join(job_departments).lower(),
        "job_requirements": " ".join(job_requirements).lower(),
        "job_description_full": " ".join(job_titles + job_descriptions + job_requirements).lower(),
    }


def _match_signal(phrase: str, sources: dict[str, str]) -> list[tuple[str, str]]:
    phrase_lower = phrase.lower()
    matches: list[tuple[str, str]] = []
    for source_name, source_text in sources.items():
        if phrase_lower and phrase_lower in source_text:
            matches.append((source_name, phrase))
    return matches


def _strip_tags(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(separator=" ")


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.lower().strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(value)
    return result
