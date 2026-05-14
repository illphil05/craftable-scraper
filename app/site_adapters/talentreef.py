from __future__ import annotations

from app.parsers.talentreef import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class TalentReefAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="talentreef",
        # apply.jobappnetwork.com is a white-label TalentReef deployment
        url_patterns=("jobappnetwork.com", "talentreef.com"),
        # React SPA — wait for job cards to render
        wait_selectors=(".job-listing", ".job-card", "[class*='job']", "a[href*='/apply/']"),
        supported_extraction_modes=("dom_list",),
        fallback_order=10,
        dom_markers=("talentreef", "jobappnetwork", "job-listing", "job-card"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
