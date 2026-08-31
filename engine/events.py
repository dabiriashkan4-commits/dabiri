from __future__ import annotations

import csv
from pathlib import Path

from .config import SETTINGS


def load_events(path: Path | None = None) -> list[dict[str, str]]:
    source = path or SETTINGS.data_dir / "events.csv"
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))
