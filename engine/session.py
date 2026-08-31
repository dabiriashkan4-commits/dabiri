from __future__ import annotations


def session_state() -> dict[str, str | bool]:
    return {
        "state": "simulated_snapshot",
        "live_feed": False,
        "executable": False,
    }
