from __future__ import annotations


def session_state(*, data_available: bool) -> dict[str, str | bool]:
    return {
        "state": "live_quote_available" if data_available else "live_quote_unavailable",
        "live_feed": data_available,
        "executable": False,
    }
