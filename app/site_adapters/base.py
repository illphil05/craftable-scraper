from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class SiteManifest:
    family: str
    variant: str = "base"
    url_patterns: tuple[str, ...] = ()
    wait_selectors: tuple[str, ...] = ()
    supported_extraction_modes: tuple[str, ...] = ("dom_list",)
    pagination_support: bool = False
    detail_page_support: bool = False
    api_capture_support: bool = False
    fallback_order: int = 100
    confidence_rules: dict[str, float] = field(default_factory=dict)
    dom_markers: tuple[str, ...] = ()
    api_markers: tuple[str, ...] = ()


class SiteAdapter:
    manifest: SiteManifest
    parser: Callable[[str, str, str | None], list[dict[str, Any]]]
    parser_version = "1.0"
    adapter_version = "1.0"
    detail_timeout_ms = 15_000
    detail_limit = 50

    def match_confidence(
        self,
        url: str,
        html: str | None = None,
        response_urls: list[str] | None = None,
    ) -> float:
        score = 0.0
        url_lower = url.lower()
        for pattern in self.manifest.url_patterns:
            if pattern.lower() in url_lower:
                score = max(score, self.manifest.confidence_rules.get("url_pattern", 0.9))
        if html:
            html_lower = html.lower()
            dom_hits = sum(1 for marker in self.manifest.dom_markers if marker.lower() in html_lower)
            if dom_hits:
                score += dom_hits * self.manifest.confidence_rules.get("dom_marker", 0.05)
        if response_urls:
            joined = "\n".join(response_urls).lower()
            api_hits = sum(1 for marker in self.manifest.api_markers if marker.lower() in joined)
            if api_hits:
                score += api_hits * self.manifest.confidence_rules.get("api_marker", 0.1)
        if score == 0 and self.manifest.family == "generic":
            score = self.manifest.confidence_rules.get("fallback", 0.01)
        return min(score, 1.0)

    async def prepare_page(self, page: Any, request_id: str) -> dict[str, Any]:
        return {"captured_response_urls": []}

    async def finalize_html(
        self,
        page: Any,
        html: str,
        page_context: dict[str, Any],
        request_id: str,
    ) -> str:
        return html

    def parse_jobs(
        self,
        html: str,
        url: str,
        company_name: str | None = None,
        *,
        match_confidence: float = 1.0,
    ) -> list[dict[str, Any]]:
        jobs = self.parser(html, url, company_name)
        return [self.annotate_job(job, "list", match_confidence) for job in jobs]

    def parse_detail(self, html: str) -> dict[str, Any] | None:
        return None

    async def enrich_jobs(
        self,
        page: Any,
        jobs: list[dict[str, Any]],
        request_id: str,
        *,
        detail_limit: int | None = None,
        detail_timeout_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        parse_detail = getattr(self, "parse_detail", None)
        if not callable(parse_detail) or parse_detail is SiteAdapter.parse_detail:
            return jobs

        effective_detail_limit = self.detail_limit if detail_limit is None else detail_limit
        effective_detail_timeout_ms = self.detail_timeout_ms if detail_timeout_ms is None else detail_timeout_ms

        for job in jobs[: effective_detail_limit]:
            job_url = job.get("url")
            if not job_url:
                continue
            try:
                await page.goto(job_url, wait_until="domcontentloaded", timeout=effective_detail_timeout_ms)
                await page.wait_for_timeout(1_500)
                detail_html = await page.content()
                enrichment = parse_detail(detail_html) or {}
                for key, value in enrichment.items():
                    if value is None:
                        continue
                    job[key] = value
                    self._append_field_evidence(
                        job,
                        key,
                        value,
                        source_page_type="detail",
                        extraction_channel="parser:detail",
                        extraction_confidence=0.85,
                    )
            except Exception:
                continue
        return jobs

    def annotate_job(
        self,
        job: dict[str, Any],
        source_page_type: str,
        match_confidence: float,
    ) -> dict[str, Any]:
        job.setdefault("canonical_title", job.get("title"))
        job.setdefault("source_site_family", self.manifest.family)
        job.setdefault("source_site_variant", self.manifest.variant)
        job.setdefault("source_confidence", round(match_confidence, 2))
        job.setdefault("extraction_method", f"adapter:{self.manifest.family}:{self.manifest.variant}")
        job.setdefault("raw_source_ref", job.get("url"))
        job.setdefault("_field_evidence", [])
        for field_name in (
            "title",
            "canonical_title",
            "location",
            "department",
            "snippet",
            "url",
            "source_site_family",
            "source_site_variant",
            "source_confidence",
            "extraction_method",
            "raw_source_ref",
        ):
            value = job.get(field_name)
            if value in (None, "", []):
                continue
            self._append_field_evidence(
                job,
                field_name,
                value,
                source_page_type=source_page_type,
                extraction_channel="parser:list",
                extraction_confidence=job.get("source_confidence", 0.9),
            )
        return job

    def _append_field_evidence(
        self,
        job: dict[str, Any],
        field_name: str,
        value: Any,
        *,
        source_page_type: str,
        extraction_channel: str,
        extraction_confidence: float,
        ) -> None:
        evidence = job.setdefault("_field_evidence", [])
        if isinstance(value, str):
            raw_value = value
        else:
            try:
                raw_value = json.dumps(value, sort_keys=True)
            except TypeError:
                raw_value = str(value)
        if any(
            e.get("field_name") == field_name
            and e.get("normalized_value") == raw_value
            and e.get("source_page_type") == source_page_type
            for e in evidence
        ):
            return
        evidence.append(
            {
                "field_name": field_name,
                "source_page_type": source_page_type,
                "extraction_channel": extraction_channel,
                "raw_value": raw_value,
                "normalized_value": raw_value,
                "extraction_confidence": round(float(extraction_confidence), 2),
                "parser_version": self.parser_version,
                "adapter_version": self.adapter_version,
            }
        )


async def collect_shadow_dom(page: Any) -> str:
    return await page.evaluate(
        """() => {
            const parts = [];
            function walk(root) {
                root.querySelectorAll('*').forEach(el => {
                    if (el.shadowRoot) {
                        parts.push(el.shadowRoot.innerHTML);
                        walk(el.shadowRoot);
                    }
                });
            }
            walk(document);
            return parts.join('\\n');
        }"""
    )
