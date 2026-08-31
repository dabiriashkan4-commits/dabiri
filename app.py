from __future__ import annotations

import json
from typing import Any

from engine.analysis import build_analysis
from engine.config import SETTINGS
from main import render_dashboard


try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
except ImportError:  # Safe import fallback for minimal/offline environments.
    FastAPI = None  # type: ignore[assignment]


def health_payload() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "provider": SETTINGS.provider,
        "mode": SETTINGS.mode,
        "synthetic_fallback": False,
        "executable": False,
    }


class FallbackASGI:
    """Small dependency-free ASGI fallback used only when FastAPI is absent."""

    routes: list[Any] = []

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            return
        path = scope.get("path", "/")
        if path == "/health":
            body = json.dumps(health_payload(), ensure_ascii=False, allow_nan=False).encode("utf-8")
            content_type, status = b"application/json; charset=utf-8", 200
        elif path == "/api/results":
            body = json.dumps(build_analysis(), ensure_ascii=False, allow_nan=False).encode("utf-8")
            content_type, status = b"application/json; charset=utf-8", 200
        elif path == "/":
            body = render_dashboard(build_analysis()).encode("utf-8")
            content_type, status = b"text/html; charset=utf-8", 200
        else:
            body, content_type, status = b'{"detail":"Not Found"}', b"application/json", 404
        headers = [(b"content-type", content_type), (b"cache-control", b"no-store")]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})


if FastAPI is not None:
    app = FastAPI(
        title="Ashkan Gold Hub — Live Market Data",
        description="Fail-closed, non-executable XAUUSD market-data dashboard",
        version="1.0.0",
    )

    @app.get("/", include_in_schema=False, response_class=HTMLResponse)
    def dashboard() -> HTMLResponse:
        return HTMLResponse(render_dashboard(build_analysis()), headers={"Cache-Control": "no-store"})

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return health_payload()

    @app.get("/api/results")
    def api_results() -> JSONResponse:
        return JSONResponse(build_analysis(), headers={"Cache-Control": "no-store"})
else:
    app = FallbackASGI()


FASTAPI_AVAILABLE = FastAPI is not None
