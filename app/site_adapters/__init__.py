from __future__ import annotations

import importlib
import pkgutil
from typing import Iterable

from app.site_adapters.base import SiteAdapter

_REGISTRY: list[SiteAdapter] = []
_DISCOVERED = False


def register_adapter(cls):
    _REGISTRY.append(cls())
    return cls


def _ensure_loaded() -> None:
    global _DISCOVERED
    if _DISCOVERED:
        return
    for module_info in pkgutil.walk_packages(__path__, prefix=f"{__name__}."):
        module_name = module_info.name
        if module_name.endswith(".base"):
            continue
        importlib.import_module(module_name)
    _DISCOVERED = True


def iter_adapters() -> Iterable[SiteAdapter]:
    _ensure_loaded()
    return list(_REGISTRY)


def get_adapter(url: str, html: str | None = None, response_urls: list[str] | None = None) -> SiteAdapter:
    _ensure_loaded()
    ranked = sorted(
        _REGISTRY,
        key=lambda adapter: (
            adapter.match_confidence(url, html=html, response_urls=response_urls),
            -adapter.manifest.fallback_order,
        ),
        reverse=True,
    )
    return ranked[0]


def adapter_count(*, include_generic: bool = False) -> int:
    _ensure_loaded()
    if include_generic:
        return len(_REGISTRY)
    return len([adapter for adapter in _REGISTRY if adapter.manifest.family != "generic"])
