from __future__ import annotations

from app.parsers.jazzhr import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class JazzHRAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="jazzhr",
        url_patterns=("applytojob.com", "jazz.co"),
        wait_selectors=(".opening", ".opening-title", "#openings", "[class*='opening']"),
        supported_extraction_modes=("dom_list",),
        fallback_order=10,
        dom_markers=("applytojob", "jazz.co", "opening-job-title", "jazzhr"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
