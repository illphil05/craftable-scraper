from __future__ import annotations

from app.parsers.ukg import parse
from app.site_adapters import register_adapter
from app.site_adapters.base import SiteAdapter, SiteManifest, collect_shadow_dom


@register_adapter
class UKGAdapter(SiteAdapter):
    manifest = SiteManifest(
        family="ukg",
        url_patterns=("ultipro.com",),
        wait_selectors=(
            "div[data-automation='opportunity']",
            "a[data-automation='job-title']",
            "a[href*='OpportunityDetail']",
        ),
        supported_extraction_modes=("dom_list", "api_capture", "shadow_dom"),
        api_capture_support=True,
        fallback_order=10,
        dom_markers=("data-automation=\"opportunity\"", "OpportunityDetail"),
        api_markers=("OpportunityDetail", "ultipro", "jobboard"),
        confidence_rules={"url_pattern": 0.95, "dom_marker": 0.02, "api_marker": 0.02},
    )
    parser = staticmethod(parse)

    async def prepare_page(self, page, request_id: str) -> dict[str, list[str]]:
        captured_bodies: list[str] = []
        captured_urls: list[str] = []

        async def capture_response(response):
            try:
                resp_url = response.url
                content_type = response.headers.get("content-type", "")
                if any(
                    ext in resp_url.lower()
                    for ext in (".css", ".png", ".jpg", ".gif", ".svg", ".woff", ".ttf", ".ico")
                ):
                    return
                if "json" in content_type or "html" in content_type or "xml" in content_type or "text/plain" in content_type:
                    body = await response.text()
                    if body and len(body) > 100:
                        captured_bodies.append(body)
                        captured_urls.append(f"{response.status} {resp_url[:200]}")
            except Exception:
                return

        page.on("response", capture_response)
        return {"captured_response_urls": captured_urls, "captured_response_bodies": captured_bodies}

    async def finalize_html(self, page, html: str, page_context: dict[str, list[str]], request_id: str) -> str:
        await page.wait_for_timeout(3_000)
        try:
            shadow_html = await collect_shadow_dom(page)
            if shadow_html and len(shadow_html) > 100:
                html += "\n" + shadow_html
        except Exception:
            pass
        for response_body in page_context.get("captured_response_bodies", []):
            html += "\n" + response_body
        return html
