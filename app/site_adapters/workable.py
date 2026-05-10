from __future__ import annotations

from app.parsers.workable import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class WorkableAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="workable",
        url_patterns=("apply.workable.com", "workable.com/j/"),
        wait_selectors=("[data-ui='job-summary']", ".jobs-list li"),
        supported_extraction_modes=("dom_list",),
        fallback_order=20,
        dom_markers=("workable", "whr-item", "apply.workable.com"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
