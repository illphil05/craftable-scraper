from __future__ import annotations

from app.parsers.ashby import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class AshbyAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="ashby",
        url_patterns=("jobs.ashbyhq.com",),
        wait_selectors=("[data-testid='job-list-item']", ".ashby-job-posting-brief-list"),
        supported_extraction_modes=("dom_list",),
        fallback_order=15,
        dom_markers=("ashby-job-posting", "__NEXT_DATA__", "jobPosting"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
