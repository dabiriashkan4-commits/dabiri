# Inspection v1.0

- Verify a valid provider fixture produces `live_market_data` and preserves timestamps.
- Verify stale, malformed, non-finite and wrong-instrument quotes are rejected.
- Verify provider failure returns `null`, `WAIT`, and `VETO` without numeric fallback.
- Verify indicators, candles, sentiment, positioning and events remain unavailable without validated sources.
- Verify strict JSON, Persian RTL HTML, FastAPI routes and ASGI responses.
- Run a real provider smoke test separately from deterministic unit tests.
