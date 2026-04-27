from __future__ import annotations

from app.parsers.workday import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class WorkdayAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="workday",
        url_patterns=("workdayjobs", "myworkday"),
        wait_selectors=("[data-automation-id='jobTitle']", "a[data-automation-id]"),
        supported_extraction_modes=("dom_list", "embedded_json"),
        fallback_order=10,
        dom_markers=("data-automation-id", '"title"'),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
