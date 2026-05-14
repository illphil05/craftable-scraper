from __future__ import annotations

from app.parsers.bamboohr import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class BambooHRAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="bamboohr",
        url_patterns=("bamboohr.com",),
        # Wait for either new or classic UI job list elements
        wait_selectors=(
            ".BambooHR-ATS-Jobs-item",
            ".ResposiveTable",
            "a[href*='view.php']",
            "[class*='BambooHR']",
        ),
        supported_extraction_modes=("dom_list",),
        fallback_order=10,
        dom_markers=("bamboohr.com", "BambooHR-ATS", "ResposiveTable"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
