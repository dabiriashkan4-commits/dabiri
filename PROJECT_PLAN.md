# Live market-data conversion

## Objective

Display only source-observed XAUUSD values and fail closed whenever freshness or validity cannot be proven.

## Implemented controls

1. Server-side Gold API quote retrieval over HTTPS.
2. Instrument, currency, positivity, finiteness, timestamp and freshness validation.
3. Thirty-second in-process cache.
4. No numeric fallback and no derived indicators without real history.
5. Explicit `WAIT` plus `CAUTION`/`VETO` when evidence is incomplete.
6. Dynamic dashboard and API responses with trade execution disabled.
