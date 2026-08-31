from __future__ import annotations


def assess_risk(volatility_ratio: float, event_count: int) -> dict[str, object]:
    reasons: list[str] = ["synthetic data is non-executable"]
    verdict = "CAUTION"
    if volatility_ratio >= 1.25:
        reasons.append("elevated synthetic volatility")
    if event_count:
        reasons.append("demo events require reassessment")
    if volatility_ratio >= 1.5 or event_count >= 2:
        verdict = "VETO"
    return {"verdict": verdict, "reasons": reasons, "trade_execution": False}
