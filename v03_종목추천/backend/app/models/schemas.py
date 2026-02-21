from datetime import datetime

from pydantic import BaseModel


class StockEntry(BaseModel):
    ticker: str
    name: str
    category: str
    pool_type: str  # "core" | "trending"


class StockPool(BaseModel):
    updated_at: str
    market: str  # "US" | "KR"
    stocks: list[StockEntry]


class DivergenceSignal(BaseModel):
    ticker: str
    name: str
    market: str
    category: str
    signal_type: str  # "regular_bullish" | "hidden_bullish" | "regular_bearish" | "hidden_bearish"
    signal_label: str  # "Bull" | "H Bull" | "Bear" | "H Bear"
    detected_at: datetime
    price_at_signal: float
    rsi_at_signal: float
    current_price: float
    price_change_pct: float


class ScanResult(BaseModel):
    scanned_at: datetime
    total_stocks: int
    signals_found: int
    scan_duration_sec: float
    signals: list[DivergenceSignal]


class ScanStatus(BaseModel):
    last_scan: datetime | None
    next_scan: datetime | None
    is_scanning: bool
