from __future__ import annotations

import hmac
import math
import os
import re
import time
from collections import deque
from typing import Any, Mapping

MAX_TITLE_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 8000
MAX_LOCATION_LENGTH = 120
MAX_PRICE = 1_000_000_000


class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = {}

    def allow_request(self, key: str) -> bool:
        now = time.monotonic()
        bucket = self._requests.setdefault(key, deque())

        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()

        if len(bucket) >= self.max_requests:
            return False

        bucket.append(now)
        return True


def get_auth_credentials(secrets: Mapping[str, Any] | None = None) -> tuple[str, str]:
    username = os.getenv("APP_USERNAME", "").strip()
    password = os.getenv("APP_PASSWORD", "").strip()

    if (not username or not password) and secrets is not None:
        try:
            username = str(secrets.get("APP_USERNAME", "")).strip()
            password = str(secrets.get("APP_PASSWORD", "")).strip()
        except Exception:
            username = ""
            password = ""

    if not username or not password:
        raise RuntimeError("APP_USERNAME and APP_PASSWORD must be configured through environment variables or Streamlit secrets")
    return username, password


def authenticate_user(username: str, password: str, expected_username: str | None = None, expected_password: str | None = None) -> bool:
    if expected_username is None or expected_password is None:
        expected_username, expected_password = get_auth_credentials()

    return bool(username) and bool(password) and hmac.compare_digest(username, expected_username) and hmac.compare_digest(password, expected_password)


def get_client_identity(headers: Mapping[str, str] | None = None) -> str:
    if headers is None:
        return "local"

    for key in ("x-forwarded-for", "x-real-ip", "cf-connecting-ip"):
        value = headers.get(key)
        if value:
            return value.split(",")[0].strip()

    return "local"


def validate_listing_input(title: str, description: str, price: Any, location: str) -> tuple[str, str, float, str]:
    """Validate and normalize listing fields before downstream processing."""
    if not isinstance(title, str) or not isinstance(description, str) or not isinstance(location, str):
        raise ValueError("title, description, and location must be strings")

    if not title.strip() or not description.strip() or not location.strip():
        raise ValueError("title, description, and location are required")

    combined_text = f"{title}{description}{location}"
    if any(ord(ch) < 32 and ch not in "\t\n\r" for ch in combined_text):
        raise ValueError("input contains unsupported control characters")

    normalized_title = re.sub(r"\s+", " ", title.strip())
    normalized_description = re.sub(r"\s+", " ", description.strip())
    normalized_location = re.sub(r"\s+", " ", location.strip())

    if len(normalized_title) > MAX_TITLE_LENGTH:
        raise ValueError("title is too long")
    if len(normalized_description) > MAX_DESCRIPTION_LENGTH:
        raise ValueError("description is too long")
    if len(normalized_location) > MAX_LOCATION_LENGTH:
        raise ValueError("location is too long")

    if isinstance(price, bool) or price is None:
        raise ValueError("price must be numeric")

    try:
        numeric_price = float(price)
    except (TypeError, ValueError) as exc:
        raise ValueError("price must be numeric") from exc

    if not math.isfinite(numeric_price):
        raise ValueError("price must be a finite number")
    if numeric_price < 0:
        raise ValueError("price cannot be negative")
    if numeric_price > MAX_PRICE:
        raise ValueError("price is too large")

    return normalized_title, normalized_description, numeric_price, normalized_location
