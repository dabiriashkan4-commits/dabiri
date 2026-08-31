from __future__ import annotations

from typing import Any


def notify_disabled(payload: dict[str, Any]) -> dict[str, object]:
    """Deliberately does not contact external services."""
    return {"sent": False, "reason": "notifications_disabled", "decision": payload.get("decision")}
