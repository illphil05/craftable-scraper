from __future__ import annotations

from app.parsers.jobvite import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class JobviteAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="jobvite",
        url_patterns=("jobs.jobvite.com",),
        wait_selectors=(".jv-job-list-name", "[class*='JobListItem']"),
        supported_extraction_modes=("dom_list",),
        fallback_order=20,
        dom_markers=("jv-job-list", "jobvite", "careers.jobvite.com"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
