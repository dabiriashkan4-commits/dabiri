from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from statistics import fmean
from typing import Any

from .config import SETTINGS
from .data import cot_demo, synthetic_ohlc
from .events import load_events
from .risk import assess_risk
from .sentiment import score_sentiment
from .session import session_state
from .signals import synthesize_signal


def _simple_average(values: list[float], window: int) -> float:
    return round(fmean(values[-window:]), 2)


def _true_ranges(candles: list[dict[str, Any]]) -> list[float]:
    ranges: list[float] = []
    previous_close: float | None = None
    for candle in candles:
        high, low = float(candle["high"]), float(candle["low"])
        if previous_close is None:
            value = high - low
        else:
            value = max(high - low, abs(high - previous_close), abs(low - previous_close))
        ranges.append(value)
        previous_close = float(candle["close"])
    return ranges


def _assert_finite(value: Any) -> None:
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("Non-finite value in analysis payload")
    if isinstance(value, dict):
        for child in value.values():
            _assert_finite(child)
    elif isinstance(value, list):
        for child in value:
            _assert_finite(child)


def build_analysis() -> dict[str, Any]:
    candles = synthetic_ohlc()
    closes = [float(row["close"]) for row in candles]
    events = load_events()
    ma_fast = _simple_average(closes, 5)
    ma_slow = _simple_average(closes, 20)
    trend = "bullish" if ma_fast > ma_slow else "bearish" if ma_fast < ma_slow else "neutral"
    true_ranges = _true_ranges(candles)
    current_tr = true_ranges[-1]
    average_tr = fmean(true_ranges[-14:])
    volatility_ratio = round(current_tr / average_tr, 3) if average_tr else 0.0
    risk = assess_risk(volatility_ratio, len(events))
    signal = synthesize_signal(trend, str(risk["verdict"]))
    payload: dict[str, Any] = {
        "metadata": {
            "instrument": SETTINGS.instrument,
            "provider": SETTINGS.provider,
            "mode": SETTINGS.mode,
            "data_label": "SYNTHETIC / DEMO / SIMULATED",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "timezone": SETTINGS.timezone,
            "live_data": False,
            "executable": False,
        },
        "decision": signal,
        "market": {
            "last_close": closes[-1],
            "ma_5": ma_fast,
            "ma_20": ma_slow,
            "trend": trend,
            "volatility_ratio": volatility_ratio,
        },
        "sentiment": score_sentiment(closes),
        "positioning": cot_demo(),
        "events": events,
        "risk": risk,
        "session": session_state(),
        "candles": candles,
        "safety": {
            "analysis_only": True,
            "trade_execution": False,
            "financial_advice": False,
        },
    }
    _assert_finite(payload)
    return payload
