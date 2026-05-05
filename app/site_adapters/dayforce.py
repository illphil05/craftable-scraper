from __future__ import annotations

from app.parsers.dayforce import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class DayforceAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="dayforce",
        url_patterns=("dayforcehcm.com",),
        wait_selectors=(),
        supported_extraction_modes=("embedded_json",),
        fallback_order=10,
        dom_markers=("__NEXT_DATA__", "jobPostingContent"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
