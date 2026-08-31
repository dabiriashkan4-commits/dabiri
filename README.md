# Ashkan Gold Hub — Synthetic Demo

A deterministic, non-executable XAUUSD analysis demo with:

- a Persian/RTL standalone HTML dashboard;
- strict JSON output with no `NaN` or `Infinity`;
- a FastAPI app when FastAPI is installed;
- a dependency-free ASGI fallback when it is not;
- Render configuration and a Netlify-ready static directory.

> Important: every price, event, position and signal is synthetic/simulated. The project has no live feed, broker connection, order execution or personalized financial advice.

## Local run

```bash
python main.py
python -m unittest discover -s tests -v
uvicorn app:app --host 0.0.0.0 --port 8000
```

Routes exposed by the FastAPI build:

- `/` — generated Persian dashboard
- `/health` — health and provider state
- `/api/results` — strict generated JSON

## Render deployment

1. Push this directory to a Git repository.
2. In Render, create a Blueprint from `render.yaml`, or create a Python Web Service.
3. Build command: `pip install -r requirements.txt`
4. Start command: `python main.py && uvicorn app:app --host 0.0.0.0 --port $PORT`
5. Health check: `/health`

The repository pins Python 3.12 in `.python-version` for reproducible dependency support. No secrets are required. `autoDeploy` is intentionally disabled in `render.yaml` so deployment stays an explicit owner action.

## Fast static deployment

Run `python main.py`, then publish only the generated `static-site/` directory. For Netlify Drop, drag `static-site/` into the Netlify Drop interface. This static route contains the same clear synthetic/demo labels and does not expose the API.

## Provenance

The source project referenced in the request was unavailable locally and its signed GapGPT link could not be retrieved. This implementation was reconstructed from the supplied file list and acceptance criteria; it does not claim to be a byte-for-byte recovery of the unavailable source.
