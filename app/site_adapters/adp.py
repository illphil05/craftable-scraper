from __future__ import annotations

from app.parsers.adp import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class ADPAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="adp",
        url_patterns=("workforcenow.adp.com",),
        wait_selectors=(
            "[class*='jobTitle']",
            "[class*='job-title']",
            "[class*='jobCard']",
            "[data-testid*='job']",
        ),
        supported_extraction_modes=("dom_list",),
        fallback_order=10,
        dom_markers=("workforcenow.adp.com", "mascsr", "mdf/recruitment", "adp-job"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
