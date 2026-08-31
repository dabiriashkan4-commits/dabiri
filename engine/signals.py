from __future__ import annotations


def synthesize_signal(trend: str, risk_verdict: str) -> dict[str, str]:
    if risk_verdict in {"VETO", "CAUTION"}:
        return {"decision": "WAIT", "bias": trend, "confidence": "low"}
    return {"decision": "WAIT", "bias": trend, "confidence": "low"}
