"""HMAC-signed outbound webhook dispatcher — Enhancement 8.

Supported events:
  job.opened         Fired when new jobs appear for a tracked company
  job.closed         Fired when jobs disappear
  scrape.failed      Fired when a scheduled scrape errors
  company.discovered Fired when a new candidate enters the discovery queue

Webhooks are stored in the `webhooks` table.  Each delivery signs the payload
with HMAC-SHA256 using the per-hook secret and sends it as X-Signature header.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time

import httpx

from app.db import list_webhooks
from app.logging_config import get_logger

log = get_logger("webhook_dispatcher")

SUPPORTED_EVENTS = frozenset(
    {"job.opened", "job.closed", "scrape.failed", "company.discovered"}
)

# How long (seconds) to wait for a webhook endpoint to respond
_TIMEOUT_S = 10.0
# Maximum retries per delivery
_MAX_RETRIES = 2


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def dispatch(event: str, payload: dict) -> None:
    """Fire all active webhooks subscribed to *event* (best-effort, non-blocking)."""
    if event not in SUPPORTED_EVENTS:
        log.warning("Unknown webhook event %r — skipping dispatch", event)
        return

    hooks = await list_webhooks(event_type=event)
    if not hooks:
        return

    envelope = {
        "event": event,
        "timestamp": int(time.time()),
        "payload": payload,
    }
    body = json.dumps(envelope, separators=(",", ":")).encode()

    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        for hook in hooks:
            secret = hook.get("secret", "")
            sig = _sign(secret, body)
            headers = {
                "Content-Type": "application/json",
                "X-Event": event,
                "X-Signature": f"sha256={sig}",
            }
            for attempt in range(_MAX_RETRIES + 1):
                try:
                    resp = await client.post(hook["url"], content=body, headers=headers)
                    if resp.status_code < 400:
                        log.debug(
                            "Webhook %s → %s: %d", event, hook["url"], resp.status_code
                        )
                        break
                    log.warning(
                        "Webhook %s → %s: HTTP %d (attempt %d)",
                        event, hook["url"], resp.status_code, attempt + 1,
                    )
                except Exception as exc:
                    log.warning(
                        "Webhook %s → %s failed (attempt %d): %s",
                        event, hook["url"], attempt + 1, exc,
                    )
