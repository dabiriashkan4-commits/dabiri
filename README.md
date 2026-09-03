# بررسی طلا اشکان دبیری — XAUUSD Research Desk

The canonical dashboard is https://dabiriashkan4-commits.github.io/dabiri/.
Its single bilingual interface is in `docs/`; the older FastAPI application below is retained as a legacy implementation, not a second production dashboard.

## Published dashboard

- Technical: completed GC=F futures candles, H1/H4/D1, EMA20/50, Wilder RSI14, ATR14 and observed support/resistance. Futures prices are not presented as spot prices.
- Fundamentals: FRED rates/CPI, official Federal Reserve H.15 fallback for yields and effective funds rate, and Yahoo dollar index. Each observation retains its actual date and source.
- News: dated official Federal Reserve releases and speeches; coverage is explicitly partial.
- Sentiment: weekly CFTC managed-money positioning, VIX and S&P 500. ETF flows and options positioning are unavailable, not inferred.
- Calendar: official BLS calendar when accessible. Failure is a risk warning, never evidence of no upcoming events.
- Liquidity: estimated zones derived from futures candles and mapped to the spot reference at calculation time. Attraction scores are uncalibrated model scores, **not probabilities** or observed order-book liquidity. Zones remain fixed until recalculation; crossings and expiry are labelled.
- Risk and scenarios: transparent automated data-quality checks and conditional scenarios. These are not fresh independent AI-agent reports. The project agents remain available for explicitly requested comprehensive research; this static site does not run them. No trades are executed.

GitHub Actions attempts a source refresh every ten minutes (schedules may be delayed). The browser attempts quote refresh every minute and ages status labels without a successful refresh. Source outages produce explicit unavailable fields; there are no fabricated replacements. A previously verified cached snapshot is clearly aged. WAIT remains the displayed conclusion pending independent research.

To verify and preview this version:

```bash
python -m unittest discover -s tests -p test_pages_data.py -v
node --test tests/pages_client.test.cjs
python scripts/build_pages_data.py
python -m http.server 8765 --directory docs
```

## Legacy server implementation

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
