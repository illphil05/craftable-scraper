"""Parser registry — auto-populated via @register_parser decorator.

Each parser module calls `register_parser(url_pattern, wait_selectors)(parse_fn)`.
Adding a new ATS requires only a single new parser file — no changes to this
module or to scraper.py.
"""
from __future__ import annotations

from typing import Callable

# Maps URL pattern → (parse_fn, wait_selectors_list)
_REGISTRY: dict[str, tuple[Callable, list[str]]] = {}


def register_parser(url_pattern: str, wait_selectors: list[str] | None = None):
    """Decorator that registers a parse function under the given URL pattern.

    Usage::

        @register_parser("greenhouse.io", [".job-post", ".opening"])
        def parse(html, url, company_name=None):
            ...
    """
    def decorator(fn: Callable) -> Callable:
        _REGISTRY[url_pattern] = (fn, wait_selectors or [])
        return fn
    return decorator


def get_parser(url: str) -> Callable:
    """Return the best parser for *url*, falling back to the generic parser."""
    _ensure_loaded()
    url_lower = url.lower()
    for pattern, (parser, _) in _REGISTRY.items():
        if pattern in url_lower:
            return parser
    from app.parsers.generic import parse
    return parse


def get_parser_name(url: str) -> str:
    """Return the short name of the parser that would handle *url*."""
    _ensure_loaded()
    url_lower = url.lower()
    for pattern in _REGISTRY:
        if pattern in url_lower:
            return pattern.split(".")[0]
    return "generic"


def get_wait_selectors(url: str) -> list[str]:
    """Return ATS-specific CSS selectors to wait for after page load."""
    _ensure_loaded()
    url_lower = url.lower()
    for pattern, (_, selectors) in _REGISTRY.items():
        if pattern in url_lower:
            return selectors
    return []


def parser_count() -> int:
    """Total number of registered ATS-specific parsers (excludes generic)."""
    _ensure_loaded()
    return len(_REGISTRY)


def _ensure_loaded() -> None:
    """Import all parser sub-modules so their @register_parser calls fire."""
    if _REGISTRY:
        return
    # Explicit imports guarantee registration order; generic is always fallback.
    import app.parsers.paylocity  # noqa: F401
    import app.parsers.icims  # noqa: F401
    import app.parsers.workday  # noqa: F401
    import app.parsers.greenhouse  # noqa: F401
    import app.parsers.lever  # noqa: F401
    import app.parsers.ukg  # noqa: F401
    import app.parsers.smartrecruiters  # noqa: F401
