from __future__ import annotations

from app.parsers.smartrecruiters import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class SmartRecruitersAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="smartrecruiters",
        url_patterns=("smartrecruiters.com",),
        wait_selectors=("li.opening-job", ".details-title", "a.link--block"),
        supported_extraction_modes=("dom_list", "json_ld"),
        fallback_order=10,
        dom_markers=("opening-job", "details-title", "JobPosting"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
