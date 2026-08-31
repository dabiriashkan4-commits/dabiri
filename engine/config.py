from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    instrument: str = "XAUUSD"
    provider: str = "synthetic"
    mode: str = "demo"
    timezone: str = "Asia/Tehran"
    horizon: str = "educational snapshot"
    data_dir: Path = ROOT / "data"
    output_dir: Path = ROOT / "output"
    static_dir: Path = ROOT / "static-site"


SETTINGS = Settings()
