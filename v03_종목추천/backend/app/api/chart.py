"""Chart data API: returns OHLCV, RSI, pivots, and divergence signals for Lightweight Charts."""

import logging
import re
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.data_fetcher import fetch_candles
from app.core.krx_lookup import get_name_by_ticker, preload_async, resolve_korean_name, resolve_korean_number
from app.core.rsi_divergence import detect_divergences_v2
from app.core.tsr import compute_tsr
from app.models.schemas import (
    CandleData,
    ChartDataResponse,
    DivergenceLine,
    PivotPoint,
    RsiPoint,
    SignalMarker,
    TsrDataResponse,
    TsrPivotMarkerResp,
    TsrSrZoneResp,
    TsrTrendLineResp,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chart", tags=["chart"])

_COLORS = {
    "regular_bullish": "#26a69a",
    "hidden_bullish": "#4dd0e1",
    "regular_bearish": "#ef5350",
    "hidden_bearish": "#ff8a65",
}

# TradingView ticker -> yfinance ticker mapping
_TV_TO_YF: dict[str, str] = {
    # Futures
    "NQ1!": "NQ=F",
    "ES1!": "ES=F",
    "YM1!": "YM=F",
    "RTY1!": "RTY=F",
    "CL1!": "CL=F",
    "GC1!": "GC=F",
    "SI1!": "SI=F",
    "ZB1!": "ZB=F",
    "ZN1!": "ZN=F",
    "6E1!": "EURUSD=X",
    "6J1!": "JPY=X",
    "BTC1!": "BTC-USD",
    "ETH1!": "ETH-USD",
    # Common name aliases
    "NASDAQ": "^NDX",
    "NASDAQ100": "^NDX",
    "NDX": "^NDX",
    "SP500": "^GSPC",
    "S&P500": "^GSPC",
    "SPX": "^GSPC",
    "DOW": "^DJI",
    "DOWJONES": "^DJI",
    "DJI": "^DJI",
    "RUSSELL": "^RUT",
    "RUSSELL2000": "^RUT",
    "VIX": "^VIX",
    "GOLD": "GC=F",
    "OIL": "CL=F",
    "SILVER": "SI=F",
    "BITCOIN": "BTC-USD",
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "ETHEREUM": "ETH-USD",
    "EURUSD": "EURUSD=X",
    "USDJPY": "JPY=X",
}

# Start KRX lookup cache loading in background (so first request is fast)
preload_async()

ET = ZoneInfo("US/Eastern")
KST = ZoneInfo("Asia/Seoul")

# Regex: 6-digit Korean stock number (with optional .KS/.KQ)
_KR_NUM_RE = re.compile(r"^\d{6}$")
# Regex: contains Korean characters
_KR_CHAR_RE = re.compile(r"[\uac00-\ud7a3]")


_UTC = ZoneInfo("UTC")


def _ticker_tz(ticker: str) -> ZoneInfo:
    """Return the native timezone for a ticker (used for naive timestamps).

    data_fetcher strips tz info, so naive timestamps are in the exchange's local time.
    yfinance returns different timezones per asset class:
      Korean stocks (.KS/.KQ) → KST
      Crypto (-USD like BTC-USD) → UTC
      Forex (=X like EURUSD=X) → UTC
      US stocks, futures (=F), indices (^) → US/Eastern
    """
    if ticker.endswith((".KS", ".KQ")):
        return KST
    if ticker.endswith("-USD") or ticker.endswith("=X"):
        return _UTC
    return ET


def _to_epoch(ts: pd.Timestamp, tz: ZoneInfo = ET) -> int:
    """Convert a pandas Timestamp to UNIX epoch seconds (UTC).

    If the timestamp is tz-naive, localize to the given timezone first.
    nonexistent/ambiguous handles DST transitions (e.g. BTC 24/7 data).
    """
    if ts.tzinfo is None:
        ts = ts.tz_localize(tz, nonexistent="shift_forward", ambiguous=False)
    return int(ts.timestamp())


def _get_stock_name(yf_ticker: str) -> str | None:
    """Get display name for a ticker. Korean → KRX lookup, others → yfinance info."""
    if yf_ticker.endswith((".KS", ".KQ")):
        return get_name_by_ticker(yf_ticker)
    try:
        info = yf.Ticker(yf_ticker).info or {}
        return info.get("shortName") or info.get("longName")
    except Exception:
        return None


def _resolve_ticker(raw: str) -> str:
    """Resolve TradingView-style tickers, Korean names, and stock numbers to yfinance.

    Uses dynamic KRX lookup (pykrx) covering ALL ~2800 KOSPI/KOSDAQ stocks.
    """
    stripped = raw.strip()
    upper = stripped.upper()

    # 1. TradingView mapping
    if upper in _TV_TO_YF:
        return _TV_TO_YF[upper]

    # 2. Korean name → dynamic KRX lookup (all KOSPI + KOSDAQ)
    if _KR_CHAR_RE.search(stripped):
        resolved = resolve_korean_name(stripped)
        if resolved:
            return resolved
        raise HTTPException(
            status_code=404,
            detail=f"'{stripped}' 종목을 찾을 수 없습니다. "
                   f"종목번호 6자리(예: 005930)를 입력해주세요.",
        )

    # 3. 6-digit Korean stock number → dynamic KRX lookup (auto .KS/.KQ)
    if _KR_NUM_RE.match(stripped):
        resolved = resolve_korean_number(stripped)
        if resolved:
            return resolved
        # Not in KRX cache, try .KS first (validate_ticker will try .KQ fallback)
        return f"{stripped}.KS"

    return stripped


class TickerValidation(BaseModel):
    valid: bool
    ticker: str          # resolved yfinance ticker
    original: str        # what the user typed
    name: str | None = None


@router.get("/validate/{ticker}", response_model=TickerValidation)
async def validate_ticker(ticker: str):
    """Quick check if a ticker exists in yfinance.
    Resolves TradingView tickers, Korean names (삼성전자), and stock numbers (005930).
    """
    resolved = _resolve_ticker(ticker)
    try:
        t = yf.Ticker(resolved)
        hist = t.history(period="5d", interval="1d")
        if hist.empty:
            # If resolved to .KS and failed, try .KQ
            if resolved.endswith(".KS"):
                alt = resolved.replace(".KS", ".KQ")
                t2 = yf.Ticker(alt)
                hist2 = t2.history(period="5d", interval="1d")
                if not hist2.empty:
                    info = t2.info or {}
                    name = info.get("shortName") or info.get("longName")
                    return TickerValidation(valid=True, ticker=alt, original=ticker, name=name)
            return TickerValidation(valid=False, ticker=resolved, original=ticker)
        info = t.info or {}
        name = info.get("shortName") or info.get("longName")
        return TickerValidation(valid=True, ticker=resolved, original=ticker, name=name)
    except Exception:
        return TickerValidation(valid=False, ticker=resolved, original=ticker)


_VALID_INTERVALS = {"15m", "1h", "4h", "1d", "1w"}


@router.get("/{ticker}", response_model=ChartDataResponse)
async def get_chart_data(
    ticker: str,
    interval: str = Query("4h", description="Candle interval: 1h, 4h, 1d"),
    days: int = Query(730, ge=1, le=730),
    rsi_period: int = Query(14, ge=2, le=50),
    lb_left: int = Query(5, ge=1, le=20),
    lb_right: int = Query(3, ge=1, le=20),
    range_lower: int = Query(5, ge=1, le=50),
    range_upper: int = Query(50, ge=10, le=200),
    lookback: int = Query(1, ge=1, le=10),
):
    """Get chart data: OHLC candles, RSI, pivots, divergence signals & lines."""
    if interval not in _VALID_INTERVALS:
        raise HTTPException(status_code=400, detail=f"Invalid interval: {interval}. Use: {_VALID_INTERVALS}")
    ticker = _resolve_ticker(ticker)
    tz = _ticker_tz(ticker)
    df = fetch_candles(ticker, interval=interval, days=days)
    if df is None or df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for {ticker}. Tried {days}d and fallbacks (500/300/180d). "
                   f"The ticker may be invalid or too recently listed.",
        )

    # Drop rows with NaN OHLC values (prevents null in JSON response)
    df = df.dropna(subset=["open", "high", "low", "close"]).copy()
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No valid candle data for {ticker}")

    signals, rsi_series, pl_dict, ph_dict = detect_divergences_v2(
        df,
        rsi_period=rsi_period,
        lb_left=lb_left,
        lb_right=lb_right,
        range_lower=range_lower,
        range_upper=range_upper,
        lookback=lookback,
    )

    # Build candles
    candles = [
        CandleData(
            time=_to_epoch(df.index[i], tz),
            open=round(df["open"].iloc[i], 4),
            high=round(df["high"].iloc[i], 4),
            low=round(df["low"].iloc[i], 4),
            close=round(df["close"].iloc[i], 4),
        )
        for i in range(len(df))
    ]

    # Build RSI points
    rsi_points = [
        RsiPoint(time=_to_epoch(df.index[i], tz), value=round(float(rsi_series.iloc[i]), 2))
        for i in range(len(rsi_series))
        if not np.isnan(rsi_series.iloc[i])
    ]

    # Build pivot points
    pivot_lows = [
        PivotPoint(
            time=_to_epoch(df.index[pv], tz),
            value=round(float(rsi_series.iloc[pv]), 2),
            price=round(float(df["low"].iloc[pv]), 4),
        )
        for _, pv in pl_dict.items()
        if pv < len(df)
    ]
    pivot_highs = [
        PivotPoint(
            time=_to_epoch(df.index[pv], tz),
            value=round(float(rsi_series.iloc[pv]), 2),
            price=round(float(df["high"].iloc[pv]), 4),
        )
        for _, pv in ph_dict.items()
        if pv < len(df)
    ]

    # Build signal markers and divergence lines
    markers = []
    div_lines = []
    for s in signals:
        is_bull = "bullish" in s.signal_type
        ts = _to_epoch(df.index[s.idx], tz)
        color = _COLORS.get(s.signal_type, "#ffffff")

        markers.append(SignalMarker(
            time=ts,
            position="belowBar" if is_bull else "aboveBar",
            color=color,
            shape="arrowUp" if is_bull else "arrowDown",
            text=s.signal_label,
        ))

        div_lines.append(DivergenceLine(
            signal_type=s.signal_type,
            signal_label=s.signal_label,
            curr_time=ts,
            curr_price=round(float(df["low"].iloc[s.idx] if is_bull else df["high"].iloc[s.idx]), 4),
            curr_rsi=round(float(rsi_series.iloc[s.idx]), 2),
            prev_time=_to_epoch(df.index[s.prev_idx], tz),
            prev_price=round(float(df["low"].iloc[s.prev_idx] if is_bull else df["high"].iloc[s.prev_idx]), 4),
            prev_rsi=round(float(rsi_series.iloc[s.prev_idx]), 2),
        ))

    return ChartDataResponse(
        ticker=ticker,
        name=_get_stock_name(ticker),
        candles=candles,
        rsi=rsi_points,
        pivot_lows=pivot_lows,
        pivot_highs=pivot_highs,
        signals=markers,
        divergence_lines=div_lines,
    )


@router.get("/{ticker}/tsr", response_model=TsrDataResponse)
async def get_tsr_data(
    ticker: str,
    interval: str = Query("4h", description="Candle interval: 1h, 4h, 1d"),
    days: int = Query(730, ge=1, le=730),
    pvt_length: int = Query(5, ge=1, le=50),
    tl_points_to_check: int = Query(3, ge=2, le=20),
    tl_max_violation: int = Query(0, ge=0, le=10),
    tl_except_bars: int = Query(3, ge=0, le=20),
    sr_points_to_check: int = Query(3, ge=1, le=20),
    sr_max_violation: int = Query(0, ge=0, le=10),
    sr_except_bars: int = Query(3, ge=0, le=20),
):
    """Get TSR indicator data: trend lines, support/resistance zones, pivot markers."""
    if interval not in _VALID_INTERVALS:
        raise HTTPException(status_code=400, detail=f"Invalid interval: {interval}. Use: {_VALID_INTERVALS}")
    ticker = _resolve_ticker(ticker)
    tz = _ticker_tz(ticker)
    df = fetch_candles(ticker, interval=interval, days=days)
    if df is None or df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for {ticker}. Tried {days}d and fallbacks (500/300/180d). "
                   f"The ticker may be invalid or too recently listed.",
        )

    df = df.dropna(subset=["open", "high", "low", "close"]).copy()
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No valid candle data for {ticker}")

    result = compute_tsr(
        df,
        pvt_length=pvt_length,
        tl_points_to_check=tl_points_to_check,
        tl_max_violation=tl_max_violation,
        tl_except_bars=tl_except_bars,
        sr_points_to_check=sr_points_to_check,
        sr_max_violation=sr_max_violation,
        sr_except_bars=sr_except_bars,
    )

    # Build candles
    candles = [
        CandleData(
            time=_to_epoch(df.index[i], tz),
            open=round(df["open"].iloc[i], 4),
            high=round(df["high"].iloc[i], 4),
            low=round(df["low"].iloc[i], 4),
            close=round(df["close"].iloc[i], 4),
        )
        for i in range(len(df))
    ]

    # Convert trend lines (idx -> epoch time)
    trend_lines = [
        TsrTrendLineResp(
            start_time=_to_epoch(df.index[tl.start_idx], tz),
            start_price=round(tl.start_price, 4),
            end_time=_to_epoch(df.index[tl.end_idx], tz),
            end_price=round(tl.end_price, 4),
            direction=tl.direction,
            is_violated=tl.is_violated,
            ext_time=_to_epoch(df.index[tl.ext_idx], tz) if tl.ext_idx is not None else None,
            ext_price=round(tl.ext_price, 4) if tl.ext_price is not None else None,
        )
        for tl in result.trend_lines
        if tl.start_idx < len(df) and tl.end_idx < len(df)
    ]

    # Convert S/R zones
    sr_zones = [
        TsrSrZoneResp(
            zone_type=z.zone_type,
            start_time=_to_epoch(df.index[z.start_idx], tz),
            end_time=_to_epoch(df.index[min(z.end_idx, len(df) - 1)], tz),
            top=round(z.top, 4),
            bottom=round(z.bottom, 4),
            price=round(z.price, 4),
        )
        for z in result.sr_zones
    ]

    # Convert pivot markers
    pivot_markers = [
        TsrPivotMarkerResp(
            time=_to_epoch(df.index[p.idx], tz),
            price=round(p.price, 4),
            pivot_type=p.pivot_type,
        )
        for p in result.pivot_markers
        if p.idx < len(df)
    ]

    return TsrDataResponse(
        ticker=ticker,
        candles=candles,
        trend_lines=trend_lines,
        sr_zones=sr_zones,
        pivot_markers=pivot_markers,
    )
