from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine.config import SETTINGS
from main import ensure_outputs


try:
    from fastapi import FastAPI
    from fastapi.responses import FileResponse, JSONResponse
except ImportError:  # Safe import fallback for minimal/offline environments.
    FastAPI = None  # type: ignore[assignment]


class FallbackASGI:
    """Small dependency-free ASGI fallback used only when FastAPI is absent."""

    routes: list[Any] = []

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            return
        path = scope.get("path", "/")
        outputs = ensure_outputs()
        if path == "/health":
            body, content_type, status = b'{"status":"ok","provider":"synthetic"}', b"application/json", 200
        elif path == "/api/results":
            body, content_type, status = outputs["results"].read_bytes(), b"application/json; charset=utf-8", 200
        elif path == "/":
            body, content_type, status = outputs["dashboard"].read_bytes(), b"text/html; charset=utf-8", 200
        else:
            body, content_type, status = b'{"detail":"Not Found"}', b"application/json", 404
        await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", content_type)]})
        await send({"type": "http.response.body", "body": body})


if FastAPI is not None:
    app = FastAPI(
        title="Ashkan Gold Hub — Synthetic Demo",
        description="Non-executable synthetic market-analysis dashboard",
        version="0.2.0",
    )

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(ensure_outputs()["dashboard"], media_type="text/html")

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {"status": "ok", "provider": SETTINGS.provider, "mode": SETTINGS.mode, "executable": False}

    @app.get("/api/results")
    def api_results() -> JSONResponse:
        path: Path = ensure_outputs()["results"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        return JSONResponse(payload)
else:
    app = FallbackASGI()


FASTAPI_AVAILABLE = FastAPI is not None
