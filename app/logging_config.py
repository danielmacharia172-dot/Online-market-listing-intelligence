from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any


def configure_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("offerup_ai")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)

    return logger


def emit_audit_event(logger: logging.Logger, event_type: str, details: dict[str, Any] | None = None) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "details": details or {},
    }
    log_line = json.dumps(payload, sort_keys=True)
    logger.info(log_line)

    audit_path = os.getenv("APP_AUDIT_LOG_PATH")
    if audit_path:
        with open(audit_path, "a", encoding="utf-8") as handle:
            handle.write(log_line + "\n")
