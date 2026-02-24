"""Chart data API: returns OHLCV, RSI, pivots, and divergence signals for Lightweight Charts."""

import logging
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.data_fetcher import fetch_4h_candles_session
from app.core.rsi_divergence import detect_divergences_v2
from app.models.schemas import (
    CandleData,
    ChartDataResponse,
    DivergenceLine,
    PivotPoint,
    RsiPoint,
    SignalMarker,
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

ET = ZoneInfo("US/Eastern")


def _to_epoch(ts: pd.Timestamp) -> int:
    """Convert a pandas Timestamp to UNIX epoch seconds (UTC).

    If the timestamp is tz-naive, localize to US/Eastern first.
    """
    if ts.tzinfo is None:
        ts = ts.tz_localize(ET)
    return int(ts.timestamp())


def _resolve_ticker(raw: str) -> str:
    """Resolve TradingView-style tickers to yfinance equivalents."""
    upper = raw.upper()
    return _TV_TO_YF.get(upper, raw)


class TickerValidation(BaseModel):
    valid: bool
    ticker: str          # resolved yfinance ticker
    original: str        # what the user typed
    name: str | None = None


@router.get("/validate/{ticker}", response_model=TickerValidation)
async def validate_ticker(ticker: str):
    """Quick check if a ticker exists in yfinance. Also resolves TradingView tickers."""
    resolved = _resolve_ticker(ticker)
    try:
        t = yf.Ticker(resolved)
        hist = t.history(period="5d", interval="1d")
        if hist.empty:
            return TickerValidation(valid=False, ticker=resolved, original=ticker)
        info = t.info or {}
        name = info.get("shortName") or info.get("longName")
        return TickerValidation(valid=True, ticker=resolved, original=ticker, name=name)
    except Exception:
        return TickerValidation(valid=False, ticker=resolved, original=ticker)


@router.get("/{ticker}", response_model=ChartDataResponse)
async def get_chart_data(
    ticker: str,
    days: int = Query(730, ge=1, le=730),
    rsi_period: int = Query(14, ge=2, le=50),
    lb_left: int = Query(5, ge=1, le=20),
    lb_right: int = Query(5, ge=1, le=20),
    range_lower: int = Query(5, ge=1, le=50),
    range_upper: int = Query(60, ge=10, le=200),
    lookback: int = Query(2, ge=1, le=10),
):
    """Get chart data: OHLC candles, RSI, pivots, divergence signals & lines."""
    ticker = _resolve_ticker(ticker)
    df = fetch_4h_candles_session(ticker, days)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for {ticker}")

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
            time=_to_epoch(df.index[i]),
            open=round(df["open"].iloc[i], 4),
            high=round(df["high"].iloc[i], 4),
            low=round(df["low"].iloc[i], 4),
            close=round(df["close"].iloc[i], 4),
        )
        for i in range(len(df))
    ]

    # Build RSI points
    rsi_points = [
        RsiPoint(time=_to_epoch(df.index[i]), value=round(float(rsi_series.iloc[i]), 2))
        for i in range(len(rsi_series))
        if not np.isnan(rsi_series.iloc[i])
    ]

    # Build pivot points
    pivot_lows = [
        PivotPoint(
            time=_to_epoch(df.index[pv]),
            value=round(float(rsi_series.iloc[pv]), 2),
            price=round(float(df["low"].iloc[pv]), 4),
        )
        for _, pv in pl_dict.items()
        if pv < len(df)
    ]
    pivot_highs = [
        PivotPoint(
            time=_to_epoch(df.index[pv]),
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
        ts = _to_epoch(df.index[s.idx])
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
            prev_time=_to_epoch(df.index[s.prev_idx]),
            prev_price=round(float(df["low"].iloc[s.prev_idx] if is_bull else df["high"].iloc[s.prev_idx]), 4),
            prev_rsi=round(float(rsi_series.iloc[s.prev_idx]), 2),
        ))

    return ChartDataResponse(
        ticker=ticker,
        candles=candles,
        rsi=rsi_points,
        pivot_lows=pivot_lows,
        pivot_highs=pivot_highs,
        signals=markers,
        divergence_lines=div_lines,
    )
