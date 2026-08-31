from __future__ import annotations

from datetime import date, timedelta
from math import sin
from typing import Any


def synthetic_ohlc(days: int = 40) -> list[dict[str, Any]]:
    """Return deterministic demo candles; values are never live market data."""
    start = date(2026, 7, 1)
    rows: list[dict[str, Any]] = []
    previous = 3320.0
    for index in range(days):
        drift = 1.7 * index
        wave = 18.0 * sin(index / 3.2)
        close = round(3320.0 + drift + wave, 2)
        open_price = round(previous, 2)
        high = round(max(open_price, close) + 9.0 + (index % 4), 2)
        low = round(min(open_price, close) - 8.0 - (index % 3), 2)
        rows.append(
            {
                "date": (start + timedelta(days=index)).isoformat(),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000 + index * 17,
            }
        )
        previous = close
    return rows


def cot_demo() -> dict[str, float | int | str]:
    return {
        "observation_date": "2026-08-25",
        "managed_money_long": 158000,
        "managed_money_short": 21000,
        "managed_money_net": 137000,
        "status": "synthetic_demo",
    }
