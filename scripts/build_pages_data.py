from __future__ import annotations

import json
import math
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.data import fetch_live_quote, normalize_quote


OUTPUT = ROOT / "docs" / "market.json"
YAHOO_SYMBOL = "GC=F"
YAHOO_API = (
    "https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF"
    "?interval=1h&range=1mo&events=history&includePrePost=false"
)
YAHOO_PAGE = "https://finance.yahoo.com/quote/GC%3DF/"


@dataclass(frozen=True)
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float


def _positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _fetch_json(url: str) -> dict[str, Any]:
    fixture = os.getenv("YAHOO_HISTORY_INPUT_FILE") if url == YAHOO_API else None
    if fixture:
        payload = json.loads(Path(fixture).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("historical fixture is not an object")
        return payload
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "AshkanGoldHub/2.0"},
        method="GET",
    )
    with urlopen(request, timeout=20) as response:
        if getattr(response, "status", 200) != 200:
            raise RuntimeError(f"upstream HTTP {getattr(response, 'status', 'unknown')}")
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("upstream payload is not an object")
    return payload


def _history() -> tuple[list[Candle], float, str, float | None]:
    payload = _fetch_json(YAHOO_API)
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not isinstance(result, dict):
        raise RuntimeError("historical market response is unavailable")
    meta = result.get("meta") or {}
    timestamps = result.get("timestamp") or []
    series = (((result.get("indicators") or {}).get("quote") or [{}])[0])
    current = meta.get("regularMarketPrice")
    market_time = meta.get("regularMarketTime")
    if not _positive(current) or not _positive(market_time):
        raise RuntimeError("historical market quote is invalid")
    opens, highs, lows, closes = (
        series.get("open") or [],
        series.get("high") or [],
        series.get("low") or [],
        series.get("close") or [],
    )
    candles: list[Candle] = []
    for index, timestamp in enumerate(timestamps):
        values = (
            timestamp,
            opens[index] if index < len(opens) else None,
            highs[index] if index < len(highs) else None,
            lows[index] if index < len(lows) else None,
            closes[index] if index < len(closes) else None,
        )
        if all(_positive(value) for value in values) and float(values[2]) >= float(values[3]):
            candles.append(
                Candle(
                    int(values[0]),
                    float(values[1]),
                    float(values[2]),
                    float(values[3]),
                    float(values[4]),
                )
            )
    if len(candles) < 80:
        raise RuntimeError("insufficient validated 1H history")
    change = meta.get("regularMarketChangePercent")
    return (
        candles[-360:],
        float(current),
        datetime.fromtimestamp(float(market_time), tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        float(change) if isinstance(change, (int, float)) and math.isfinite(change) else None,
    )


def _atr(candles: list[Candle], period: int = 14) -> float:
    ranges = []
    for candle, previous in zip(candles[1:], candles[:-1]):
        ranges.append(
            max(
                candle.high - candle.low,
                abs(candle.high - previous.close),
                abs(candle.low - previous.close),
            )
        )
    sample = ranges[-period:]
    return sum(sample) / len(sample)


def _ema(values: list[float], period: int) -> float:
    alpha = 2 / (period + 1)
    average = values[0]
    for value in values[1:]:
        average = value * alpha + average * (1 - alpha)
    return average


def _clusters(points: list[tuple[float, int]], tolerance: float) -> list[dict[str, float]]:
    clusters: list[dict[str, float]] = []
    for value, timestamp in sorted(points):
        match = next((item for item in clusters if abs(item["midpoint"] - value) <= tolerance), None)
        if match:
            touches = match["touches"]
            match["midpoint"] = (match["midpoint"] * touches + value) / (touches + 1)
            match["touches"] = touches + 1
            match["last_timestamp"] = max(match["last_timestamp"], float(timestamp))
        else:
            clusters.append({"midpoint": value, "touches": 1.0, "last_timestamp": float(timestamp)})
    return clusters


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))


def _liquidity(candles: list[Candle], spot: float, futures: float) -> dict[str, Any]:
    basis = spot - futures
    adjusted = [
        Candle(row.timestamp, row.open + basis, row.high + basis, row.low + basis, row.close + basis)
        for row in candles
    ]
    atr = _atr(adjusted)
    if not _positive(atr):
        raise RuntimeError("ATR validation failed")
    highs: list[tuple[float, int]] = []
    lows: list[tuple[float, int]] = []
    for index in range(2, len(adjusted) - 2):
        candle = adjusted[index]
        neighbors = adjusted[index - 2 : index] + adjusted[index + 1 : index + 3]
        if all(candle.high >= item.high for item in neighbors):
            highs.append((candle.high, candle.timestamp))
        if all(candle.low <= item.low for item in neighbors):
            lows.append((candle.low, candle.timestamp))

    tolerance = max(atr * 0.32, spot * 0.00012)
    half_width = max(atr * 0.18, spot * 0.00008)
    now = time.time()

    def ranked(points: list[tuple[float, int]], side: str) -> list[dict[str, float]]:
        rows = []
        for cluster in _clusters(points, tolerance):
            midpoint = cluster["midpoint"]
            if side == "above" and midpoint <= spot + half_width * 0.25:
                continue
            if side == "below" and midpoint >= spot - half_width * 0.25:
                continue
            distance_atr = abs(midpoint - spot) / atr
            recency = math.exp(-max(0.0, now - cluster["last_timestamp"]) / (3600 * 96))
            score = cluster["touches"] * 0.62 + recency * 0.78 + math.exp(-distance_atr / 2.4)
            rows.append({**cluster, "distance_atr": distance_atr, "score": score})
        return sorted(sorted(rows, key=lambda row: row["score"], reverse=True)[:5], key=lambda row: row["distance_atr"])[:2]

    upper = ranked(highs, "above")
    lower = ranked(lows, "below")
    if not upper or not lower:
        raise RuntimeError("balanced swing evidence is unavailable")

    closes = [row.close for row in adjusted]
    momentum = _clamp((closes[-1] - closes[-13]) / atr, -2.5, 2.5)
    trend = _clamp((_ema(closes[-80:], 20) - _ema(closes[-80:], 50)) / atr, -2.5, 2.5)
    upper_strength = _clamp(upper[0]["touches"] / 4, 0.25, 1.5)
    lower_strength = _clamp(lower[0]["touches"] / 4, 0.25, 1.5)
    distance_difference = _clamp(lower[0]["distance_atr"] - upper[0]["distance_atr"], -2, 2)
    logit = 0.33 * momentum + 0.24 * trend + 0.2 * (upper_strength - lower_strength) + 0.24 * distance_difference
    raw_upper = 100 / (1 + math.exp(-logit))
    confidence = "medium" if len(adjusted) >= 240 and min(upper[0]["touches"], lower[0]["touches"]) >= 2 else "low"
    floor, ceiling = (30, 70) if confidence == "medium" else (40, 60)
    upper_probability = round(_clamp(raw_upper, floor, ceiling))

    zones = []
    for side, rows in (("above", upper), ("below", lower)):
        for index, cluster in enumerate(rows):
            zones.append(
                {
                    "side": side,
                    "low": round(cluster["midpoint"] - half_width, 4),
                    "high": round(cluster["midpoint"] + half_width, 4),
                    "midpoint": round(cluster["midpoint"], 4),
                    "touches": int(cluster["touches"]),
                    "rank": "primary" if index == 0 else "secondary",
                    "model_probability": (upper_probability if side == "above" else 100 - upper_probability) if index == 0 else None,
                }
            )
    zones.sort(key=lambda row: row["midpoint"], reverse=True)
    return {
        "timeframe": "1H",
        "lookback_bars": len(adjusted),
        "atr": round(atr, 4),
        "confidence": confidence,
        "directional_bias": "upward" if upper_probability >= 56 else "downward" if upper_probability <= 44 else "balanced",
        "upper_probability": upper_probability,
        "lower_probability": 100 - upper_probability,
        "zones": zones,
        "proxy_adjusted": True,
        "methodology": "Clustered 1H swing highs/lows, touch count, ATR distance, 12-hour momentum and EMA20/EMA50 trend.",
        "limitation": "Price-action liquidity proxy; not an order book or a measurement of resting orders.",
    }


def build_payload() -> dict[str, Any]:
    quote_fixture = os.getenv("GOLD_QUOTE_INPUT_FILE")
    quote = (
        normalize_quote(json.loads(Path(quote_fixture).read_text(encoding="utf-8")))
        if quote_fixture
        else fetch_live_quote()
    )
    candles, futures_price, futures_observed_at, change_percent = _history()
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "refresh_policy_seconds": 600,
        "instrument": "XAUUSD",
        "quote": {**quote, "quality": "live", "change_percent": change_percent},
        "reference": {
            "symbol": YAHOO_SYMBOL,
            "price": round(futures_price, 6),
            "observed_at": futures_observed_at,
            "provider": "Yahoo Finance · CME gold futures reference",
            "source_url": YAHOO_PAGE,
        },
        "liquidity": _liquidity(candles, float(quote["price"]), futures_price),
        "decision": "WAIT",
        "trade_execution": False,
    }


def main() -> None:
    payload = build_payload()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote docs/market.json with {len(payload['liquidity']['zones'])} liquidity zones")


if __name__ == "__main__":
    main()
