from __future__ import annotations

from app.parsers.lever import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class LeverAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="lever",
        url_patterns=("lever.co",),
        wait_selectors=(".posting-title", ".posting"),
        supported_extraction_modes=("dom_list",),
        fallback_order=10,
        dom_markers=("posting-title", "posting-name", "jobs.lever.co"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
