from __future__ import annotations

from app.parsers.generic import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class GenericAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="generic",
        variant="base",
        supported_extraction_modes=("dom_list", "json_ld"),
        fallback_order=999,
        confidence_rules={"url_pattern": 0.01, "fallback": 0.01},
    )
    parser = staticmethod(parse)
