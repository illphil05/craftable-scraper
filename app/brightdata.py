"""Bright Data REST API client.

Provides typed async access to:
  - Web Unlocker API  (unlock_url)

Environment variables:
  BRIGHTDATA_API_KEY          Required for REST calls
  BRIGHTDATA_UNLOCKER_ZONE    Zone name (default: web_unlocker1)
  BRIGHTDATA_SERP_ZONE        SERP zone name (default: serp_api1)
  BRIGHTDATA_COUNTRY          Default country code (default: us)
  BRIGHTDATA_BROWSER_WS       Kept for adapters that need a residential browser
"""
from __future__ import annotations

import os
from typing import TypedDict

import httpx

from app.logging_config import get_logger

log = get_logger("brightdata")

_UNLOCKER_ENDPOINT = "https://api.brightdata.com/request"

_DEFAULT_ZONE = os.environ.get("BRIGHTDATA_UNLOCKER_ZONE", "web_unlocker1")
_DEFAULT_COUNTRY = os.environ.get("BRIGHTDATA_COUNTRY", "us")


class BrightDataUnlockResult(TypedDict):
    status_code: int
    headers: dict
    body: str


class BrightDataError(Exception):
    """Raised when the Bright Data API returns an error."""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _api_key() -> str:
    key = os.environ.get("BRIGHTDATA_API_KEY", "")
    if not key:
        raise BrightDataError("BRIGHTDATA_API_KEY is not set")
    return key


async def unlock_url(
    url: str,
    *,
    format: str = "json",
    data_format: str | None = None,
    country: str | None = None,
    zone: str | None = None,
    timeout: float = 30.0,
) -> BrightDataUnlockResult:
    """Fetch *url* via Bright Data Web Unlocker REST API.

    Returns a BrightDataUnlockResult with status_code, headers, and body.
    Raises BrightDataError on API-level failures.
    """
    resolved_zone = zone or _DEFAULT_ZONE
    resolved_country = country or _DEFAULT_COUNTRY

    payload: dict = {
        "zone": resolved_zone,
        "url": url,
        "format": format,
        "method": "GET",
        "country": resolved_country,
    }
    if data_format:
        payload["data_format"] = data_format

    log.debug("Bright Data unlock request: zone=%s url=%s country=%s", resolved_zone, url, resolved_country)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                _UNLOCKER_ENDPOINT,
                json=payload,
                headers={
                    "Authorization": f"Bearer {_api_key()}",
                    "Content-Type": "application/json",
                },
            )
    except httpx.TimeoutException as exc:
        raise BrightDataError(f"Bright Data request timed out for {url}: {exc}") from exc
    except httpx.RequestError as exc:
        raise BrightDataError(f"Bright Data network error for {url}: {exc}") from exc

    if response.status_code >= 500:
        raise BrightDataError(
            f"Bright Data server error {response.status_code} for {url}: {response.text[:200]}",
            status_code=response.status_code,
        )

    try:
        data = response.json()
    except Exception:
        raise BrightDataError(
            f"Bright Data returned non-JSON response ({response.status_code}) for {url}",
            status_code=response.status_code,
        )

    if response.status_code >= 400:
        raise BrightDataError(
            f"Bright Data API error {response.status_code}: {data}",
            status_code=response.status_code,
        )

    result_body = data.get("body", "")
    if not isinstance(result_body, str):
        result_body = str(result_body)

    result: BrightDataUnlockResult = {
        "status_code": data.get("status_code", response.status_code),
        "headers": data.get("headers", {}),
        "body": result_body,
    }

    log.debug(
        "Bright Data unlock result: status=%d body_size=%d",
        result["status_code"],
        len(result["body"]),
    )
    return result


def is_configured() -> bool:
    """Return True if BRIGHTDATA_API_KEY is present in the environment."""
    return bool(os.environ.get("BRIGHTDATA_API_KEY"))
