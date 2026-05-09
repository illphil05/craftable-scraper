from __future__ import annotations

from app.parsers.taleo import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class TaleoAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="taleo",
        url_patterns=("taleo.net",),
        wait_selectors=(".requisitionListInterface", "#requisitionListInterface table"),
        supported_extraction_modes=("dom_list",),
        fallback_order=25,
        dom_markers=("taleo", "requisitionListInterface", "oraclecloudhcm"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
