from __future__ import annotations

from app.parsers.greenhouse import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class GreenhouseAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="greenhouse",
        url_patterns=("greenhouse.io",),
        wait_selectors=(".job-post", ".opening", "tr.job-post"),
        supported_extraction_modes=("dom_list",),
        pagination_support=False,
        fallback_order=10,
        dom_markers=("job-post", "opening", "/jobs/"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
