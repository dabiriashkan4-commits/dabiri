# Ashkan Gold Hub — Live XAUUSD Quote

A Persian/RTL, non-executable XAUUSD dashboard that displays only validated market data.

## Data policy

- Current XAU/USD price is fetched server-side from the public Gold API endpoint.
- The provider timestamp, server fetch timestamp and quote age are preserved in the API response.
- Responses are cached for 30 seconds, following the provider guidance.
- Quotes older than five minutes, malformed values, wrong instruments and non-finite prices are rejected.
- There is no synthetic numeric fallback. If the provider is unavailable or invalid, price becomes `null` and the dashboard shows `WAIT`.
- Historical OHLC, technical indicators, economic events, sentiment and positioning remain unavailable until separately validated real-data sources are configured.
- Trade execution is always disabled.

Provider documentation: <https://gold-api.com/docs>

## Local run

```bash
python -m unittest discover -s tests -v
uvicorn app:app --host 0.0.0.0 --port 8000
```

Routes:

- `/` — dynamically rendered Persian dashboard
- `/health` — application/provider configuration state
- `/api/results` — current validated quote and explicit unavailable fields

`python main.py` can generate a timestamped offline snapshot, but the deployed FastAPI routes fetch dynamically and send `Cache-Control: no-store`.

## Render deployment

The included Blueprint uses Python 3.12 and the free Render web-service plan.

- Build: `pip install -r requirements.txt`
- Start: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`

No API secret is required for the current quote endpoint. Optional environment variables are `GOLD_API_QUOTE_URL`, `MARKET_DATA_TIMEOUT_SECONDS`, `MARKET_DATA_CACHE_SECONDS`, and `MAX_QUOTE_AGE_SECONDS`.

## Provenance

The original source project referenced in the request was unavailable locally. This implementation was reconstructed from the supplied requirements and does not claim to be a byte-for-byte recovery of that source.
