from __future__ import annotations

import json
import math
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import SETTINGS


class MarketDataError(RuntimeError):
    """Raised when a real market quote cannot be obtained or validated."""


_cache_lock = threading.Lock()
_cached_quote: dict[str, Any] | None = None
_cache_expires_at = 0.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_utc_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise MarketDataError("provider timestamp is missing")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise MarketDataError("provider timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise MarketDataError("provider timestamp has no timezone")
    return parsed.astimezone(timezone.utc)


def normalize_quote(payload: Any, *, fetched_at: datetime | None = None) -> dict[str, Any]:
    """Validate a Gold API response; never manufacture or repair market values."""
    if not isinstance(payload, dict):
        raise MarketDataError("provider response is not an object")
    if payload.get("symbol") != "XAU" or payload.get("currency") != "USD":
        raise MarketDataError("provider returned an unexpected instrument")

    price = payload.get("price")
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        raise MarketDataError("provider price is missing")
    price = float(price)
    if not math.isfinite(price) or price <= 0:
        raise MarketDataError("provider price is invalid")

    fetched = (fetched_at or _utc_now()).astimezone(timezone.utc)
    observed = _parse_utc_timestamp(payload.get("updatedAt"))
    age_seconds = (fetched - observed).total_seconds()
    if age_seconds < -120:
        raise MarketDataError("provider timestamp is unexpectedly in the future")
    if age_seconds > SETTINGS.max_quote_age_seconds:
        raise MarketDataError("provider quote is stale")

    return {
        "instrument": "XAUUSD",
        "base": "XAU",
        "quote": "USD",
        "unit": "troy_ounce",
        "price": round(price, 6),
        "observed_at": observed.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "fetched_at": fetched.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "age_seconds": round(max(0.0, age_seconds), 3),
        "provider": SETTINGS.provider,
        "source_url": SETTINGS.quote_url,
    }


def fetch_live_quote(
    *,
    opener: Callable[..., Any] = urlopen,
    fetched_at: datetime | None = None,
) -> dict[str, Any]:
    request = Request(
        SETTINGS.quote_url,
        headers={"Accept": "application/json", "User-Agent": "AshkanGoldHub/1.0"},
        method="GET",
    )
    try:
        with opener(request, timeout=SETTINGS.request_timeout_seconds) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise MarketDataError(f"provider HTTP status {status}")
            raw = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise MarketDataError("market data provider is unreachable") from exc

    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MarketDataError("provider returned invalid JSON") from exc
    return normalize_quote(decoded, fetched_at=fetched_at)


def get_live_quote(*, force_refresh: bool = False) -> dict[str, Any]:
    """Return a validated quote and honor the provider's 30-second cache guidance."""
    global _cached_quote, _cache_expires_at
    now = time.monotonic()
    with _cache_lock:
        if not force_refresh and _cached_quote is not None and now < _cache_expires_at:
            return dict(_cached_quote)
        quote = fetch_live_quote()
        _cached_quote = quote
        _cache_expires_at = time.monotonic() + SETTINGS.quote_cache_seconds
        return dict(quote)


def clear_quote_cache() -> None:
    global _cached_quote, _cache_expires_at
    with _cache_lock:
        _cached_quote = None
        _cache_expires_at = 0.0
