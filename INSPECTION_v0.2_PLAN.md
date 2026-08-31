# Inspection v0.2 plan

- Validate all generated JSON with `allow_nan=False`.
- Confirm provider and mode are `synthetic` and `demo`.
- Confirm generated HTML has `lang="fa"`, `dir="rtl"`, Plotly and Vazirmatn references.
- Parse the embedded application/json payload independently.
- Compile `main.py`, `app.py`, `engine/*.py` and `tests/test_core.py`.
- Run all unittest cases verbosely.
- Import the ASGI app, enumerate real FastAPI routes when available and perform internal GET requests.
- Verify Render start and health-check configuration without claiming a live deployment.
