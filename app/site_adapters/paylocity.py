from __future__ import annotations

from app.parsers.paylocity import parse
from app.parsers.paylocity_detail import parse_detail
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest


@register_adapter
class PaylocityAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="paylocity",
        url_patterns=("paylocity.com",),
        wait_selectors=(".job-listing-card", "a[href*='Details']", ".job-title"),
        supported_extraction_modes=("embedded_json", "dom_list", "detail"),
        detail_page_support=True,
        fallback_order=10,
        dom_markers=('"JobId"', '"JobTitle"', "HiringDepartment"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02},
    )
    parser = staticmethod(parse)
    parse_detail = staticmethod(parse_detail)
