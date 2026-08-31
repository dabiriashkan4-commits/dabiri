from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    instrument: str = "XAUUSD"
    provider: str = "gold-api.com"
    mode: str = "live_market_data"
    timezone: str = "Asia/Tehran"
    horizon: str = "current observed quote"
    quote_url: str = os.getenv("GOLD_API_QUOTE_URL", "https://api.gold-api.com/price/XAU/USD")
    request_timeout_seconds: float = float(os.getenv("MARKET_DATA_TIMEOUT_SECONDS", "8"))
    quote_cache_seconds: int = int(os.getenv("MARKET_DATA_CACHE_SECONDS", "30"))
    max_quote_age_seconds: int = int(os.getenv("MAX_QUOTE_AGE_SECONDS", "300"))
    output_dir: Path = ROOT / "output"
    static_dir: Path = ROOT / "static-site"


SETTINGS = Settings()
