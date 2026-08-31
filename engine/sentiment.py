from __future__ import annotations


def score_sentiment(closes: list[float]) -> dict[str, float | str]:
    if len(closes) < 6:
        return {"score": 0.0, "label": "neutral", "status": "insufficient_demo_history"}
    recent = closes[-1] - closes[-6]
    score = max(-1.0, min(1.0, round(recent / 100.0, 3)))
    label = "bullish" if score > 0.15 else "bearish" if score < -0.15 else "neutral"
    return {"score": score, "label": label, "status": "synthetic_demo"}
