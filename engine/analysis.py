from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Callable

from .config import SETTINGS
from .data import MarketDataError, get_live_quote
from .risk import assess_data_risk
from .session import session_state


def _assert_finite(value: Any) -> None:
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("Non-finite value in analysis payload")
    if isinstance(value, dict):
        for child in value.values():
            _assert_finite(child)
    elif isinstance(value, list):
        for child in value:
            _assert_finite(child)


def build_analysis(
    quote_loader: Callable[[], dict[str, Any]] = get_live_quote,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    quote: dict[str, Any] | None = None
    provider_error: str | None = None
    try:
        quote = quote_loader()
    except MarketDataError as exc:
        provider_error = str(exc)
    except Exception:
        provider_error = "unexpected provider failure"

    data_available = quote is not None
    risk = assess_data_risk(data_available=data_available, history_available=False)
    payload: dict[str, Any] = {
        "metadata": {
            "instrument": SETTINGS.instrument,
            "provider": SETTINGS.provider,
            "mode": SETTINGS.mode,
            "data_label": "LIVE / OBSERVED" if data_available else "LIVE SOURCE UNAVAILABLE",
            "generated_at": generated_at,
            "observed_at": quote["observed_at"] if quote else None,
            "timezone": SETTINGS.timezone,
            "live_data": data_available,
            "data_available": data_available,
            "provider_error": provider_error,
            "source_url": SETTINGS.quote_url,
            "executable": False,
        },
        "decision": {"decision": "WAIT", "bias": "neutral", "confidence": "low"},
        "market": {
            "price": quote["price"] if quote else None,
            "currency": "USD",
            "unit": "troy_ounce",
            "quote_age_seconds": quote["age_seconds"] if quote else None,
            "trend": None,
            "ma_5": None,
            "ma_20": None,
            "volatility_ratio": None,
        },
        "quote": quote,
        "technical": {
            "status": "unavailable",
            "reason": "validated historical OHLC is not configured; no indicators were calculated",
        },
        "sentiment": {
            "score": None,
            "label": "unavailable",
            "status": "no validated live sentiment source configured",
        },
        "positioning": {
            "status": "unavailable",
            "reason": "no validated live positioning source configured",
        },
        "events": [],
        "events_status": "no validated live economic-calendar source configured",
        "risk": risk,
        "session": session_state(data_available=data_available),
        "candles": [],
        "safety": {
            "analysis_only": True,
            "trade_execution": False,
            "financial_advice": False,
            "synthetic_fallback": False,
        },
    }
    _assert_finite(payload)
    return payload
