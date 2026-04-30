"""Structured JSON logging configuration for the Craftable Scraper service."""
import json
import logging
import logging.handlers
import os
import uuid
from datetime import datetime, timezone


LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.environ.get("LOG_DIR", "/data/logs")
LOG_TO_FILE = os.environ.get("LOG_TO_FILE", "true").lower() not in ("false", "0", "no")


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name.removeprefix("craftable."),
            "msg": record.message,
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        extra_skip = {"name", "msg", "args", "levelname", "levelno", "pathname",
                      "filename", "module", "exc_info", "exc_text", "stack_info",
                      "lineno", "funcName", "created", "msecs", "relativeCreated",
                      "thread", "threadName", "processName", "process", "message",
                      "taskName"}
        for key, val in record.__dict__.items():
            if key not in extra_skip:
                payload[key] = val
        return json.dumps(payload, default=str)


def _build_handlers() -> dict:
    handlers: dict = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
            "stream": "ext://sys.stdout",
        },
    }
    if LOG_TO_FILE:
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
        except PermissionError:
            # Log directory not writable (e.g. test environments) — console only.
            return handlers
        handlers["file"] = {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "formatter": "json_fmt",
            "filename": os.path.join(LOG_DIR, "scraper.log"),
            "when": "midnight",
            "backupCount": 14,
            "encoding": "utf-8",
        }
    return handlers


def _handler_names() -> list[str]:
    return list(_build_handlers().keys())


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json_fmt": {
            "()": "app.logging_config._JsonFormatter",
        },
        "plain": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%SZ",
        },
    },
    "handlers": _build_handlers(),
    "loggers": {
        "craftable": {
            "handlers": _handler_names(),
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"level": "WARNING"},
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}


def setup_logging() -> None:
    import logging.config as lc
    lc.dictConfig(LOGGING_CONFIG)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"craftable.{name}")


def make_request_id() -> str:
    return uuid.uuid4().hex[:12]
