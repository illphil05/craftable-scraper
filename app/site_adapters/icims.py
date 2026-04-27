from __future__ import annotations

from app.parsers.icims import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class ICIMSAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="icims",
        url_patterns=("icims.com",),
        wait_selectors=(".iCIMS_JobsTable", "a[href*='job']"),
        supported_extraction_modes=("dom_list", "embedded_json"),
        fallback_order=10,
        dom_markers=("iCIMS_JobsTable", "iCIMS_Header", '"jobTitle"'),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
