from __future__ import annotations

import asyncio
import json
import math
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as application
import main as generator
from engine.analysis import build_analysis
from engine.data import MarketDataError, normalize_quote
from main import render_dashboard


FETCHED_AT = datetime(2026, 8, 31, 15, 42, 21, tzinfo=timezone.utc)
PROVIDER_FIXTURE = {
    "currency": "USD",
    "currencySymbol": "$",
    "exchangeRate": 1.0,
    "name": "Gold",
    "price": 4431.0,
    "symbol": "XAU",
    "updatedAt": "2026-08-31T15:42:08Z",
}
VALID_QUOTE = normalize_quote(PROVIDER_FIXTURE, fetched_at=FETCHED_AT)


async def asgi_get(path: str) -> tuple[int, bytes, dict[bytes, bytes]]:
    messages: list[dict[str, object]] = []
    request_sent = False

    async def receive() -> dict[str, object]:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, object]) -> None:
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "scheme": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8000),
    }
    await application.app(scope, receive, send)
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    headers = dict(start.get("headers", []))
    return int(start["status"]), body, headers


class CoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = build_analysis(lambda: dict(VALID_QUOTE))
        self.app_patch = patch.object(application, "build_analysis", return_value=self.payload)
        self.app_patch.start()

    def tearDown(self) -> None:
        self.app_patch.stop()

    def test_payload_serializes_as_strict_json(self) -> None:
        encoded = json.dumps(self.payload, allow_nan=False)
        self.assertIsInstance(json.loads(encoded), dict)

    def test_payload_uses_validated_live_quote(self) -> None:
        self.assertEqual(self.payload["metadata"]["provider"], "gold-api.com")
        self.assertEqual(self.payload["metadata"]["mode"], "live_market_data")
        self.assertTrue(self.payload["metadata"]["live_data"])
        self.assertEqual(self.payload["market"]["price"], 4431.0)
        self.assertFalse(self.payload["safety"]["synthetic_fallback"])

    def test_unavailable_provider_fails_closed(self) -> None:
        def unavailable() -> dict[str, object]:
            raise MarketDataError("provider offline")

        payload = build_analysis(unavailable)
        self.assertIsNone(payload["market"]["price"])
        self.assertFalse(payload["metadata"]["data_available"])
        self.assertEqual(payload["decision"]["decision"], "WAIT")
        self.assertEqual(payload["risk"]["verdict"], "VETO")

    def test_quote_validation_rejects_stale_or_wrong_data(self) -> None:
        stale = dict(PROVIDER_FIXTURE, updatedAt="2026-08-31T15:00:00Z")
        with self.assertRaises(MarketDataError):
            normalize_quote(stale, fetched_at=FETCHED_AT)
        wrong_symbol = dict(PROVIDER_FIXTURE, symbol="BTC")
        with self.assertRaises(MarketDataError):
            normalize_quote(wrong_symbol, fetched_at=FETCHED_AT)
        invalid_price = dict(PROVIDER_FIXTURE, price=float("nan"))
        with self.assertRaises(MarketDataError):
            normalize_quote(invalid_price, fetched_at=FETCHED_AT)

    def test_all_floats_are_finite(self) -> None:
        def visit(value: object) -> None:
            if isinstance(value, float):
                self.assertTrue(math.isfinite(value))
            elif isinstance(value, dict):
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(self.payload)

    def test_no_indicators_are_invented_without_history(self) -> None:
        self.assertIsNone(self.payload["market"]["trend"])
        self.assertIsNone(self.payload["market"]["ma_5"])
        self.assertIsNone(self.payload["sentiment"]["score"])
        self.assertEqual(self.payload["candles"], [])
        self.assertEqual(self.payload["decision"]["decision"], "WAIT")

    def test_outputs_are_created_and_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = SimpleNamespace(output_dir=root / "output", static_dir=root / "static-site")
            with patch.object(generator, "SETTINGS", settings):
                paths = generator.generate_outputs(self.payload)
            self.assertTrue(paths["results"].is_file())
            self.assertTrue(paths["dashboard"].is_file())
            self.assertTrue(paths["static"].is_file())
            json.loads(paths["results"].read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))

    def test_dashboard_is_rtl_and_clearly_live(self) -> None:
        html = render_dashboard(self.payload)
        self.assertIn('<html lang="fa" dir="rtl">', html)
        self.assertIn("Vazirmatn", html)
        self.assertIn("LIVE / OBSERVED", html)
        self.assertIn("fallback ساختگی", html)
        self.assertNotIn("SYNTHETIC / DEMO", html)

    def test_embedded_payload_is_strict_json(self) -> None:
        html = render_dashboard(self.payload)
        match = re.search(r'<script type="application/json" id="dashboard-data">(.*?)</script>', html, re.DOTALL)
        self.assertIsNotNone(match)
        parsed = json.loads(match.group(1), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        self.assertEqual(parsed["metadata"]["provider"], "gold-api.com")

    def test_app_imports_and_exposes_real_routes(self) -> None:
        self.assertTrue(callable(application.app))
        if application.FASTAPI_AVAILABLE:
            paths = {route.path for route in application.app.routes}
            self.assertTrue({"/", "/health", "/api/results"}.issubset(paths))

    def test_asgi_root_smoke(self) -> None:
        status, body, headers = asyncio.run(asgi_get("/"))
        self.assertEqual(status, 200)
        self.assertIn(b"text/html", headers.get(b"content-type", b""))
        self.assertIn("LIVE / OBSERVED".encode(), body)

    def test_asgi_api_smoke(self) -> None:
        status, body, _ = asyncio.run(asgi_get("/api/results"))
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result["market"]["price"], 4431.0)
        self.assertFalse(result["safety"]["synthetic_fallback"])

    def test_asgi_health_smoke(self) -> None:
        status, body, _ = asyncio.run(asgi_get("/health"))
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result["provider"], "gold-api.com")
        self.assertFalse(result["synthetic_fallback"])


if __name__ == "__main__":
    unittest.main()
