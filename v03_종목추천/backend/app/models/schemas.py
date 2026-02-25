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


# ============================================================
# Chart API response models
# ============================================================

class CandleData(BaseModel):
    time: int      # UNIX epoch seconds
    open: float
    high: float
    low: float
    close: float

class RsiPoint(BaseModel):
    time: int
    value: float

class PivotPoint(BaseModel):
    time: int
    value: float    # RSI value at pivot
    price: float    # price at pivot (low or high)

class SignalMarker(BaseModel):
    time: int
    position: str   # "belowBar" or "aboveBar"
    color: str
    shape: str      # "arrowUp" or "arrowDown"
    text: str

class DivergenceLine(BaseModel):
    signal_type: str
    signal_label: str
    curr_time: int
    curr_price: float
    curr_rsi: float
    prev_time: int
    prev_price: float
    prev_rsi: float

class ChartDataResponse(BaseModel):
    ticker: str
    candles: list[CandleData]
    rsi: list[RsiPoint]
    pivot_lows: list[PivotPoint]
    pivot_highs: list[PivotPoint]
    signals: list[SignalMarker]
    divergence_lines: list[DivergenceLine]


# ============================================================
# TSR (Trend Lines, Supports, Resistances) response models
# ============================================================

class TsrTrendLineResp(BaseModel):
    start_time: int
    start_price: float
    end_time: int
    end_price: float
    direction: str        # "up" or "down"
    is_violated: bool
    ext_time: int | None = None
    ext_price: float | None = None

class TsrSrZoneResp(BaseModel):
    zone_type: str        # "support" or "resistance"
    start_time: int
    end_time: int
    top: float
    bottom: float
    price: float

class TsrPivotMarkerResp(BaseModel):
    time: int
    price: float
    pivot_type: str       # "high" or "low"

class TsrDataResponse(BaseModel):
    ticker: str
    candles: list[CandleData]
    trend_lines: list[TsrTrendLineResp]
    sr_zones: list[TsrSrZoneResp]
    pivot_markers: list[TsrPivotMarkerResp]
