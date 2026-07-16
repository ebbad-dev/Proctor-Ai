from __future__ import annotations

import contextvars
import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any

request_id_var = contextvars.ContextVar("request_id", default="")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "") or request_id_var.get(""),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(logs_dir: str, level: str = "INFO") -> logging.Logger:
    os.makedirs(logs_dir, exist_ok=True)
    logger = logging.getLogger("proctorai")
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = RotatingFileHandler(
        os.path.join(logs_dir, "api_access.log"),
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    console = logging.StreamHandler()
    console.setFormatter(JsonFormatter())
    logger.addHandler(console)
    logger.propagate = False
    return logger


def log_event(logger: logging.Logger, event: str, *, level: str = "info", **fields: Any) -> None:
    method = getattr(logger, level, logger.info)
    method(event, extra={"request_id": fields.pop("request_id", ""), "extra_fields": fields})
