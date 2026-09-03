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
from scripts.research_feeds import collect, stamp, yahoo_result


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


def _history(daily=False) -> tuple[list[Candle], float, str, float | None]:
    if daily:
        result = yahoo_result("GC=F", "1d", "1y")
    else:
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
    if meta.get("symbol") != YAHOO_SYMBOL or meta.get("currency") != "USD":
        raise RuntimeError("unexpected historical instrument")
    if market_time > time.time() + 120:
        raise RuntimeError("future reference quote")
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
        if (all(_positive(value) for value in values)
                and values[0] + (86400 if daily else 3600) <= time.time()
                and values[3] <= min(values[1], values[4]) <= max(values[1], values[4]) <= values[2]):
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
    if len({c.timestamp for c in candles}) != len(candles):
        raise RuntimeError("duplicate candles")
    candles.sort(key=lambda c: c.timestamp)
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


def _rsi(values, period=14):
    if len(values) < period+1:
        return None
    diffs = [b-a for a, b in zip(values, values[1:])]
    gain = sum(max(0, d) for d in diffs[:period])/period
    loss = sum(max(0, -d) for d in diffs[:period])/period
    for d in diffs[period:]:
        gain = (gain*(period-1)+max(0, d))/period
        loss = (loss*(period-1)+max(0, -d))/period
    return 50.0 if gain == loss == 0 else 100.0 if loss == 0 else 100-100/(1+gain/loss)


def _h4(candles):
    groups = {}
    for c in candles:
        groups.setdefault(c.timestamp//14400, []).append(c)
    result = []
    for rows in groups.values():
        rows.sort(key=lambda x: x.timestamp)
        if len(rows) == 4 and all(b.timestamp-a.timestamp == 3600 for a, b in zip(rows, rows[1:])):
            result.append(Candle(rows[0].timestamp, rows[0].open, max(c.high for c in rows), min(c.low for c in rows), rows[-1].close))
    return result


def technical(candles, seconds):
    if len(candles) < 50:
        return {"status": "unavailable", "reason": "Insufficient completed candles"}
    closes = [c.close for c in candles]
    ema20, ema50 = _ema(closes, 20), _ema(closes, 50)
    observed = datetime.fromtimestamp(candles[-1].timestamp+seconds, timezone.utc)
    return {"status": "available" if (datetime.now(timezone.utc)-observed).total_seconds() < max(96*3600, seconds*3) else "stale",
            "observed_at": stamp(observed), "bars": len(candles), "close": closes[-1], "ema20": round(ema20, 3), "ema50": round(ema50, 3),
            "rsi14": round(_rsi(closes), 2), "atr14": round(_atr(candles), 3),
            "support": min(c.low for c in candles[-20:]), "resistance": max(c.high for c in candles[-20:]),
            "trend": "bullish" if closes[-1] > ema20 > ema50 else "bearish" if closes[-1] < ema20 < ema50 else "mixed",
            "source": "Yahoo Finance · GC=F futures (not spot)", "source_url": YAHOO_PAGE}


def risk_gate(payload, now):
    reasons = ["unreviewed", "proxy", "uncalibrated", "news_coverage", "missing_options_etf"]
    quote = payload.get("quote")
    if not quote or (now-datetime.fromisoformat(quote["observed_at"].replace("Z", "+00:00"))).total_seconds() > 300:
        reasons.append("quote_unavailable")
    if not payload.get("liquidity") or payload["liquidity"].get("status") != "available":
        reasons.append("liquidity_unavailable")
    r = payload.get("research", {})
    if any(payload.get("technical", {}).get(k, {}).get("status") != "available" for k in ["H1", "H4", "D1"]):
        reasons.append("technical_gap")
    if any(r.get(k, {}).get("status") != "available" for k in ["real10y", "nominal10y", "nominal2y", "dxy", "fed_upper", "cpi"]):
        reasons.append("macro_gap")
    if r.get("positioning", {}).get("status") in ["unavailable", "stale", None]:
        reasons.append("positioning_gap")
    if r.get("calendar", {}).get("status") != "available":
        reasons.append("calendar_gap")
    else:
        for e in r["calendar"].get("items", []):
            delta = (datetime.fromisoformat(e["scheduled_at"].replace("Z", "+00:00"))-now).total_seconds()
            if -3600 <= delta <= 24*3600:
                reasons.append("event_risk")
                break
    return {"verdict": "VETO" if any(k in reasons for k in ["quote_unavailable", "liquidity_unavailable", "event_risk"]) else "CAUTION",
            "reasons": reasons, "kind": "automated_data_gate_not_agent_review", "checked_at": stamp(now)}


def build_payload() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    payload = {"schema_version": 2, "generated_at": stamp(now), "refresh_policy_seconds": 600,
               "instrument": "XAUUSD", "quote": None, "reference": None, "liquidity": None,
               "technical": {}, "errors": {}, "decision": "WAIT", "trade_execution": False}
    try:
        fixture = os.getenv("GOLD_QUOTE_INPUT_FILE")
        q = normalize_quote(json.loads(Path(fixture).read_text(encoding="utf-8"))) if fixture else fetch_live_quote()
        payload["quote"] = {**q, "quality": "live" if q["age_seconds"] <= 90 else "delayed"}
    except Exception:
        payload["errors"]["quote"] = "Source unavailable or quote failed freshness validation"
    try:
        candles, price, observed, change = _history()
        payload["reference"] = {"symbol": YAHOO_SYMBOL, "price": price, "observed_at": observed,
                                "change_percent": change, "provider": "Yahoo Finance · GC=F", "source_url": YAHOO_PAGE}
        payload["technical"]["H1"] = technical(candles, 3600)
        payload["technical"]["H4"] = technical(_h4(candles), 14400)
        if payload["quote"] and (now-datetime.fromisoformat(observed.replace("Z", "+00:00"))).total_seconds() <= 3600:
            liq = _liquidity(candles, payload["quote"]["price"], price)
            liq.update(status="available", observed_at=observed, calculated_at=stamp(),
                       reference_spot=payload["quote"]["price"], kind="uncalibrated_attraction_score", calibrated_probability=None)
            # Scores are model outputs, not calibrated probabilities of a price path.
            liq["upper_score"] = liq.pop("upper_probability")
            liq["lower_score"] = liq.pop("lower_probability")
            for zone in liq["zones"]:
                zone["attraction_score"] = zone.pop("model_probability")
            payload["liquidity"] = liq
    except Exception:
        payload["errors"]["history"] = "Source unavailable or invalid completed history"
    try:
        daily, _, _, _ = _history(daily=True)
        payload["technical"]["D1"] = technical(daily, 86400)
    except Exception:
        payload["technical"]["D1"] = {"status": "unavailable"}
    payload["research"] = collect(datetime.now(timezone.utc))
    payload["risk"] = risk_gate(payload, datetime.now(timezone.utc))
    payload["generated_at"] = stamp()
    return payload


def main() -> None:
    payload = build_payload()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    print("Wrote validated data snapshot; risk gate:", payload["risk"]["verdict"])


if __name__ == "__main__":
    main()
