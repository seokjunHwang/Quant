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
    name: str | None = None
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


# ── Step 1: 테마 발굴 & 랭킹 ──


class TrendTheme(BaseModel):
    rank: int
    theme: str
    description: str
    urgency_score: float       # 자금 쏠림 강도 (0-20)
    duration_score: float      # 지속 기간 전망 (0-20)
    clarity_score: float       # 수혜 경로 명확성 (0-20)
    policy_score: float        # 정책/규제 순풍 (0-20)
    consensus_score: float     # 시장 컨센서스 (0-20)
    total_score: float         # 합산 (0-100)
    reasoning: str


# ── Step 2: 종목 발굴 & 랭킹 ──


class DiscoveredStock(BaseModel):
    ticker: str
    name: str
    theme: str
    theme_rank: int
    stock_rank: int
    purity_score: float        # 테마 순수도 (0-25)
    growth_score: float        # 매출 성장률 (0-20)
    volume_score: float        # 거래량 급증 (0-20)
    position_score: float      # 가격 위치 (0-15)
    catalyst_score: float      # 촉매 유무 (0-10)
    financial_score: float     # 재무 건전성 (0-10)
    total_score: float         # 합산 (0-100)
    reasoning: str
    market_cap_estimate: str


# ── Step 3: 종목 검증 ──


class ValidationWarning(BaseModel):
    warning_type: str          # "dilution" | "short_interest" | "insider_selling" | "sec_issue" | "revenue_decline"
    description: str


class ValidatedStock(BaseModel):
    ticker: str
    name: str
    theme: str
    theme_rank: int
    stock_rank: int
    discovery_score: float
    market_cap: float
    avg_daily_value: float
    warnings: list[ValidationWarning]
    warning_count: int
    passed: bool
    fail_reason: str | None = None


# ── Step 5: 최종 랭킹 ──


class FinalRanking(BaseModel):
    rank: int
    ticker: str
    name: str
    theme: str
    theme_rank: int
    discovery_score: float
    rsi_bonus: float
    warning_penalty: float
    final_score: float
    market_cap: float
    warnings: list[ValidationWarning]
    rsi_signal: str | None = None


class TrendScanResult(BaseModel):
    scanned_at: datetime
    themes: list[TrendTheme]
    discovered_count: int
    validated_count: int
    final_rankings: list[FinalRanking]
    scan_duration_sec: float


class TrendScanStatus(BaseModel):
    last_scan: datetime | None
    is_scanning: bool
