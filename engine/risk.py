from __future__ import annotations


def assess_data_risk(*, data_available: bool, history_available: bool) -> dict[str, object]:
    reasons: list[str] = []
    if not data_available:
        reasons.append("validated live quote is unavailable")
    if not history_available:
        reasons.append("validated historical OHLC is unavailable")
    reasons.append("technical, macro, news and sentiment evidence is incomplete")
    verdict = "VETO" if not data_available else "CAUTION"
    return {"verdict": verdict, "reasons": reasons, "trade_execution": False}
