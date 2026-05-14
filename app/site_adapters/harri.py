from __future__ import annotations

from app.parsers.harri import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class HarriAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="harri",
        url_patterns=("harri.com",),
        wait_selectors=(
            ".opening",
            "[class*='job-posting']",
            "[class*='harri-job']",
            "a[href*='/external/posting']",
        ),
        supported_extraction_modes=("dom_list",),
        fallback_order=10,
        dom_markers=("harri.com", "harri-", "external/posting", "external/opening"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
