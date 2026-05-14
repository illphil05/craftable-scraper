from __future__ import annotations

from app.parsers.apploi import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class ApploiAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="apploi",
        url_patterns=("apploi.com",),
        wait_selectors=(
            "h1",
            "[class*='job-title']",
            "[class*='position-title']",
            "[class*='apploi']",
        ),
        supported_extraction_modes=("dom_list",),
        fallback_order=10,
        dom_markers=("apploi.com", "apploi-", "/job/"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
