"""
RSI Divergence Detection Engine
Pine Script (rsi_divergence.pine) -> Python 1:1 port

Detects 4 types of divergence on RSI:
  - Regular Bullish:  Price Lower Low  + RSI Higher Low
  - Hidden Bullish:   Price Higher Low + RSI Lower Low
  - Regular Bearish:  Price Higher High + RSI Lower High
  - Hidden Bearish:   Price Lower High + RSI Higher High
"""

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from app.config import settings


@dataclass
class RawDivergence:
    """Internal divergence detection result before enrichment."""
    signal_type: str
    signal_label: str
    bar_index: int
    timestamp: datetime
    price: float
    rsi: float


def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI using Wilder's smoothing (matches TradingView/Pine)."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    # First average: simple mean
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    # Wilder's smoothing for subsequent values
    for i in range(period, len(close)):
        avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def find_pivot_lows(series: pd.Series, lb_left: int, lb_right: int) -> pd.Series:
    """
    Find pivot lows: series[i] is lower than all lb_left bars to the left
    and all lb_right bars to the right.
    Matches Pine: ta.pivotlow(osc, lbL, lbR)
    The pivot is confirmed at bar index (i + lb_right), looking back at bar i.
    """
    result = pd.Series(False, index=series.index)
    values = series.values

    for i in range(lb_left, len(values) - lb_right):
        val = values[i]
        if np.isnan(val):
            continue

        left_slice = values[max(0, i - lb_left):i]
        right_slice = values[i + 1:i + 1 + lb_right]

        if len(left_slice) < lb_left or len(right_slice) < lb_right:
            continue

        if np.any(np.isnan(left_slice)) or np.any(np.isnan(right_slice)):
            continue

        if np.all(val <= left_slice) and np.all(val < right_slice):
            # Pivot confirmed at i + lb_right (Pine convention: current bar when pivot is confirmed)
            confirm_idx = i + lb_right
            if confirm_idx < len(values):
                result.iloc[confirm_idx] = True

    return result


def find_pivot_highs(series: pd.Series, lb_left: int, lb_right: int) -> pd.Series:
    """
    Find pivot highs: series[i] is higher than all lb_left bars to the left
    and all lb_right bars to the right.
    Matches Pine: ta.pivothigh(osc, lbL, lbR)
    """
    result = pd.Series(False, index=series.index)
    values = series.values

    for i in range(lb_left, len(values) - lb_right):
        val = values[i]
        if np.isnan(val):
            continue

        left_slice = values[max(0, i - lb_left):i]
        right_slice = values[i + 1:i + 1 + lb_right]

        if len(left_slice) < lb_left or len(right_slice) < lb_right:
            continue

        if np.any(np.isnan(left_slice)) or np.any(np.isnan(right_slice)):
            continue

        if np.all(val >= left_slice) and np.all(val > right_slice):
            confirm_idx = i + lb_right
            if confirm_idx < len(values):
                result.iloc[confirm_idx] = True

    return result


def valuewhen(condition: pd.Series, source: pd.Series, occurrence: int = 0) -> pd.Series:
    """
    Get the value of `source` at the Nth most recent True in `condition`.
    occurrence=0 -> current True, occurrence=1 -> previous True
    Matches Pine: ta.valuewhen(cond, src, occurrence)
    """
    result = pd.Series(np.nan, index=source.index)
    true_indices = []

    for i in range(len(condition)):
        if condition.iloc[i]:
            true_indices.append(i)
        if len(true_indices) > occurrence:
            idx = true_indices[-(occurrence + 1)]
            result.iloc[i] = source.iloc[idx]

    return result


def barssince(condition: pd.Series) -> pd.Series:
    """
    Count bars since condition was last True.
    Matches Pine: ta.barssince(cond)
    """
    result = pd.Series(np.nan, index=condition.index)
    last_true = -1

    for i in range(len(condition)):
        if condition.iloc[i]:
            last_true = i
        if last_true >= 0:
            result.iloc[i] = i - last_true

    return result


def detect_divergences(
    df: pd.DataFrame,
    rsi_period: int | None = None,
    lb_left: int | None = None,
    lb_right: int | None = None,
    range_lower: int | None = None,
    range_upper: int | None = None,
) -> list[RawDivergence]:
    """
    Detect RSI divergences on OHLCV DataFrame.
    Directly ports the Pine Script logic from rsi_divergence.pine.

    Args:
        df: DataFrame with columns [open, high, low, close, volume] and DatetimeIndex
        rsi_period: RSI calculation period (default from settings: 14)
        lb_left: Pivot lookback left (default: 5)
        lb_right: Pivot lookback right (default: 5)
        range_lower: Minimum bars between pivots (default: 5)
        range_upper: Maximum bars between pivots (default: 60)

    Returns:
        List of RawDivergence objects sorted by timestamp descending (newest first)
    """
    rsi_period = rsi_period or settings.RSI_PERIOD
    lb_left = lb_left or settings.PIVOT_LOOKBACK_LEFT
    lb_right = lb_right or settings.PIVOT_LOOKBACK_RIGHT
    range_lower = range_lower or settings.RANGE_LOWER
    range_upper = range_upper or settings.RANGE_UPPER

    if len(df) < rsi_period + lb_left + lb_right + 10:
        return []

    # Normalize column names to lowercase
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    # 1. Calculate RSI
    osc = calc_rsi(df["close"], rsi_period)

    # 2. Find pivot lows and highs on RSI
    # In Pine, pivots are detected on osc with lbL/lbR lookback
    # The pivot value is at osc[lbR] (lb_right bars back from confirmation bar)
    pl_found = find_pivot_lows(osc, lb_left, lb_right)
    ph_found = find_pivot_highs(osc, lb_left, lb_right)

    # 3. Build valuewhen and barssince series
    # Pine: osc[lbR] at pivot -> the actual RSI value at the pivot point
    # When pl_found[i] is True, the pivot value is osc[i - lb_right]
    osc_at_pivot_low = pd.Series(np.nan, index=df.index)
    price_at_pivot_low = pd.Series(np.nan, index=df.index)
    for i in range(lb_right, len(df)):
        if pl_found.iloc[i]:
            osc_at_pivot_low.iloc[i] = osc.iloc[i - lb_right]
            price_at_pivot_low.iloc[i] = df["low"].iloc[i - lb_right]

    osc_at_pivot_high = pd.Series(np.nan, index=df.index)
    price_at_pivot_high = pd.Series(np.nan, index=df.index)
    for i in range(lb_right, len(df)):
        if ph_found.iloc[i]:
            osc_at_pivot_high.iloc[i] = osc.iloc[i - lb_right]
            price_at_pivot_high.iloc[i] = df["high"].iloc[i - lb_right]

    # valuewhen for pivot lows: current (occ=0) and previous (occ=1)
    vw_osc_pl_curr = valuewhen(pl_found, osc_at_pivot_low, 0)
    vw_osc_pl_prev = valuewhen(pl_found, osc_at_pivot_low, 1)
    vw_price_pl_curr = valuewhen(pl_found, price_at_pivot_low, 0)
    vw_price_pl_prev = valuewhen(pl_found, price_at_pivot_low, 1)

    # valuewhen for pivot highs
    vw_osc_ph_curr = valuewhen(ph_found, osc_at_pivot_high, 0)
    vw_osc_ph_prev = valuewhen(ph_found, osc_at_pivot_high, 1)
    vw_price_ph_curr = valuewhen(ph_found, price_at_pivot_high, 0)
    vw_price_ph_prev = valuewhen(ph_found, price_at_pivot_high, 1)

    # barssince for range check (shifted by 1 like Pine's plFound[1])
    bs_pl = barssince(pl_found.shift(1, fill_value=False))
    bs_ph = barssince(ph_found.shift(1, fill_value=False))

    results: list[RawDivergence] = []

    for i in range(lb_right, len(df)):
        # --- Pivot Low divergences ---
        if pl_found.iloc[i]:
            # Range check: previous pivot low within range
            in_range_pl = (
                not np.isnan(bs_pl.iloc[i])
                and range_lower <= bs_pl.iloc[i] <= range_upper
            )

            if in_range_pl:
                curr_osc = vw_osc_pl_curr.iloc[i]
                prev_osc = vw_osc_pl_prev.iloc[i]
                curr_price = vw_price_pl_curr.iloc[i]
                prev_price = vw_price_pl_prev.iloc[i]

                if not any(np.isnan(v) for v in [curr_osc, prev_osc, curr_price, prev_price]):
                    # Regular Bullish: price LL + RSI HL
                    if curr_price < prev_price and curr_osc > prev_osc:
                        ts = df.index[i - lb_right] if hasattr(df.index[i - lb_right], 'timestamp') else df.index[i - lb_right]
                        results.append(RawDivergence(
                            signal_type="regular_bullish",
                            signal_label="Bull",
                            bar_index=i,
                            timestamp=pd.Timestamp(ts),
                            price=float(df["close"].iloc[i - lb_right]),
                            rsi=float(osc.iloc[i - lb_right]),
                        ))

                    # Hidden Bullish: price HL + RSI LL
                    if curr_price > prev_price and curr_osc < prev_osc:
                        ts = df.index[i - lb_right]
                        results.append(RawDivergence(
                            signal_type="hidden_bullish",
                            signal_label="H Bull",
                            bar_index=i,
                            timestamp=pd.Timestamp(ts),
                            price=float(df["close"].iloc[i - lb_right]),
                            rsi=float(osc.iloc[i - lb_right]),
                        ))

        # --- Pivot High divergences ---
        if ph_found.iloc[i]:
            in_range_ph = (
                not np.isnan(bs_ph.iloc[i])
                and range_lower <= bs_ph.iloc[i] <= range_upper
            )

            if in_range_ph:
                curr_osc = vw_osc_ph_curr.iloc[i]
                prev_osc = vw_osc_ph_prev.iloc[i]
                curr_price = vw_price_ph_curr.iloc[i]
                prev_price = vw_price_ph_prev.iloc[i]

                if not any(np.isnan(v) for v in [curr_osc, prev_osc, curr_price, prev_price]):
                    # Regular Bearish: price HH + RSI LH
                    if curr_price > prev_price and curr_osc < prev_osc:
                        ts = df.index[i - lb_right]
                        results.append(RawDivergence(
                            signal_type="regular_bearish",
                            signal_label="Bear",
                            bar_index=i,
                            timestamp=pd.Timestamp(ts),
                            price=float(df["close"].iloc[i - lb_right]),
                            rsi=float(osc.iloc[i - lb_right]),
                        ))

                    # Hidden Bearish: price LH + RSI HH
                    if curr_price < prev_price and curr_osc > prev_osc:
                        ts = df.index[i - lb_right]
                        results.append(RawDivergence(
                            signal_type="hidden_bearish",
                            signal_label="H Bear",
                            bar_index=i,
                            timestamp=pd.Timestamp(ts),
                            price=float(df["close"].iloc[i - lb_right]),
                            rsi=float(osc.iloc[i - lb_right]),
                        ))

    # Sort newest first
    results.sort(key=lambda x: x.timestamp, reverse=True)
    return results
