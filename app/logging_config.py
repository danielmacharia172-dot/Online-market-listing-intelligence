from __future__ import annotations

import json
import logging
import os
from pathlib import Path
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
        try:
            audit_file = Path(audit_path)
            if audit_file.parent and not audit_file.parent.exists():
                audit_file.parent.mkdir(parents=True, exist_ok=True)
            with audit_file.open("a", encoding="utf-8") as handle:
                handle.write(log_line + "\n")
        except OSError as exc:
            logger.warning("Failed to write audit log file %s: %s", audit_path, exc)
