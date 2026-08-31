from __future__ import annotations

import asyncio
import json
import math
import re
import unittest

import app as application
from engine.analysis import build_analysis
from main import generate_outputs, render_dashboard


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
        self.payload = build_analysis()

    def test_payload_serializes_as_strict_json(self) -> None:
        encoded = json.dumps(self.payload, allow_nan=False)
        self.assertIsInstance(json.loads(encoded), dict)

    def test_payload_labels_synthetic_demo(self) -> None:
        self.assertEqual(self.payload["metadata"]["provider"], "synthetic")
        self.assertEqual(self.payload["metadata"]["mode"], "demo")
        self.assertFalse(self.payload["metadata"]["live_data"])

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

    def test_signal_is_wait_and_non_executable(self) -> None:
        self.assertEqual(self.payload["decision"]["decision"], "WAIT")
        self.assertFalse(self.payload["risk"]["trade_execution"])

    def test_outputs_are_created_and_parseable(self) -> None:
        paths = generate_outputs()
        self.assertTrue(paths["results"].is_file())
        self.assertTrue(paths["dashboard"].is_file())
        self.assertTrue(paths["static"].is_file())
        json.loads(paths["results"].read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))

    def test_dashboard_is_rtl_and_clearly_demo(self) -> None:
        html = render_dashboard(self.payload)
        self.assertIn('<html lang="fa" dir="rtl">', html)
        self.assertIn("Vazirmatn", html)
        self.assertIn("cdn.plot.ly", html)
        self.assertIn("SYNTHETIC / DEMO", html)
        self.assertIn("داده کاملاً شبیه‌سازی‌شده", html)

    def test_embedded_payload_is_strict_json(self) -> None:
        html = render_dashboard(self.payload)
        match = re.search(r'<script type="application/json" id="dashboard-data">(.*?)</script>', html, re.DOTALL)
        self.assertIsNotNone(match)
        parsed = json.loads(match.group(1), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        self.assertEqual(parsed["metadata"]["provider"], "synthetic")

    def test_app_imports_and_exposes_real_routes(self) -> None:
        self.assertTrue(callable(application.app))
        if application.FASTAPI_AVAILABLE:
            paths = {route.path for route in application.app.routes}
            self.assertTrue({"/", "/health", "/api/results"}.issubset(paths))

    def test_asgi_root_smoke(self) -> None:
        status, body, headers = asyncio.run(asgi_get("/"))
        self.assertEqual(status, 200)
        self.assertIn(b"text/html", headers.get(b"content-type", b""))
        self.assertIn("SYNTHETIC / DEMO".encode(), body)

    def test_asgi_health_smoke(self) -> None:
        status, body, _ = asyncio.run(asgi_get("/health"))
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result["provider"], "synthetic")


if __name__ == "__main__":
    unittest.main()
