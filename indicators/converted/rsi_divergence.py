"""
Auto-converted from Pine Script: rsi_divergence.pine
Converted at: 2026-02-18
Model: claude-sonnet-4-20250514
source_hash: manual_port
Verification status: verified

RSI Divergence Detection Engine
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

METADATA = {
    "name": "RSI Divergence",
    "category": "momentum",
    "default_params": {
        "rsi_period": 14,
        "lb_left": 5,
        "lb_right": 5,
        "range_lower": 5,
        "range_upper": 60,
        "lookback": 2,
    },
    "description": "RSI 피봇 기반 다이버전스 탐지 (Regular/Hidden, Bull/Bear)",
}


# ============================================================
# Dataclasses
# ============================================================

@dataclass
class RawDivergence:
    """Internal divergence detection result before enrichment."""
    signal_type: str
    signal_label: str
    bar_index: int
    timestamp: datetime
    price: float
    rsi: float


@dataclass
class ChartDivergence:
    """Divergence signal with both current and previous pivot info for line drawing."""
    signal_type: str       # regular_bullish / hidden_bullish / regular_bearish / hidden_bearish
    signal_label: str      # Bull / H.Bull / Bear / H.Bear
    idx: int               # current pivot bar index
    prev_idx: int          # previous pivot bar index
    price: float
    rsi: float
    prev_price: float
    prev_rsi: float


# ============================================================
# Core functions
# ============================================================

def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI using Wilder's smoothing (matches TradingView/Pine)."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    for i in range(period, len(close)):
        avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def find_pivot_lows(series: pd.Series, lb_left: int, lb_right: int) -> pd.Series:
    """Find pivot lows. Matches Pine: ta.pivotlow(osc, lbL, lbR)."""
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
            confirm_idx = i + lb_right
            if confirm_idx < len(values):
                result.iloc[confirm_idx] = True
    return result


def find_pivot_highs(series: pd.Series, lb_left: int, lb_right: int) -> pd.Series:
    """Find pivot highs. Matches Pine: ta.pivothigh(osc, lbL, lbR)."""
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
    """Get value of source at Nth most recent True in condition. Matches Pine: ta.valuewhen."""
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
    """Count bars since condition was last True. Matches Pine: ta.barssince."""
    result = pd.Series(np.nan, index=condition.index)
    last_true = -1
    for i in range(len(condition)):
        if condition.iloc[i]:
            last_true = i
        if last_true >= 0:
            result.iloc[i] = i - last_true
    return result


def find_pivots_indexed(
    series: pd.Series, lb_left: int, lb_right: int, mode: str,
) -> dict[int, int]:
    """Find RSI pivots. Returns: {confirm_bar: pivot_bar}. mode: 'low' or 'high'."""
    out: dict[int, int] = {}
    v = series.values
    for i in range(lb_left, len(v) - lb_right):
        if np.isnan(v[i]):
            continue
        L = v[i - lb_left:i]
        R = v[i + 1:i + 1 + lb_right]
        if len(L) < lb_left or len(R) < lb_right:
            continue
        if np.any(np.isnan(L)) or np.any(np.isnan(R)):
            continue
        if mode == "low":
            ok = np.all(v[i] <= L) and np.all(v[i] < R)
        else:
            ok = np.all(v[i] >= L) and np.all(v[i] > R)
        if ok:
            out[i + lb_right] = i
    return out


# ============================================================
# v1: Original detection (used by screener)
# ============================================================

def detect_divergences(
    df: pd.DataFrame,
    rsi_period: int = 14,
    lb_left: int = 5,
    lb_right: int = 5,
    range_lower: int = 5,
    range_upper: int = 60,
) -> list[RawDivergence]:
    """
    Detect RSI divergences on OHLCV DataFrame.
    Directly ports the Pine Script logic from rsi_divergence.pine.

    Returns:
        List of RawDivergence objects sorted by timestamp descending (newest first)
    """
    if len(df) < rsi_period + lb_left + lb_right + 10:
        return []

    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    osc = calc_rsi(df["close"], rsi_period)
    pl_found = find_pivot_lows(osc, lb_left, lb_right)
    ph_found = find_pivot_highs(osc, lb_left, lb_right)

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

    vw_osc_pl_curr = valuewhen(pl_found, osc_at_pivot_low, 0)
    vw_osc_pl_prev = valuewhen(pl_found, osc_at_pivot_low, 1)
    vw_price_pl_curr = valuewhen(pl_found, price_at_pivot_low, 0)
    vw_price_pl_prev = valuewhen(pl_found, price_at_pivot_low, 1)

    vw_osc_ph_curr = valuewhen(ph_found, osc_at_pivot_high, 0)
    vw_osc_ph_prev = valuewhen(ph_found, osc_at_pivot_high, 1)
    vw_price_ph_curr = valuewhen(ph_found, price_at_pivot_high, 0)
    vw_price_ph_prev = valuewhen(ph_found, price_at_pivot_high, 1)

    bs_pl = barssince(pl_found.shift(1, fill_value=False))
    bs_ph = barssince(ph_found.shift(1, fill_value=False))

    results: list[RawDivergence] = []

    for i in range(lb_right, len(df)):
        if pl_found.iloc[i]:
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
                    if curr_price < prev_price and curr_osc > prev_osc:
                        ts = df.index[i - lb_right]
                        results.append(RawDivergence(
                            signal_type="regular_bullish", signal_label="Bull",
                            bar_index=i, timestamp=pd.Timestamp(ts),
                            price=float(df["close"].iloc[i - lb_right]),
                            rsi=float(osc.iloc[i - lb_right]),
                        ))
                    if curr_price > prev_price and curr_osc < prev_osc:
                        ts = df.index[i - lb_right]
                        results.append(RawDivergence(
                            signal_type="hidden_bullish", signal_label="H Bull",
                            bar_index=i, timestamp=pd.Timestamp(ts),
                            price=float(df["close"].iloc[i - lb_right]),
                            rsi=float(osc.iloc[i - lb_right]),
                        ))

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
                    if curr_price > prev_price and curr_osc < prev_osc:
                        ts = df.index[i - lb_right]
                        results.append(RawDivergence(
                            signal_type="regular_bearish", signal_label="Bear",
                            bar_index=i, timestamp=pd.Timestamp(ts),
                            price=float(df["close"].iloc[i - lb_right]),
                            rsi=float(osc.iloc[i - lb_right]),
                        ))
                    if curr_price < prev_price and curr_osc > prev_osc:
                        ts = df.index[i - lb_right]
                        results.append(RawDivergence(
                            signal_type="hidden_bearish", signal_label="H Bear",
                            bar_index=i, timestamp=pd.Timestamp(ts),
                            price=float(df["close"].iloc[i - lb_right]),
                            rsi=float(osc.iloc[i - lb_right]),
                        ))

    results.sort(key=lambda x: x.timestamp, reverse=True)
    return results


# ============================================================
# v2: Enhanced detection with lookback parameter (for chart API)
# ============================================================

def detect_divergences_v2(
    df: pd.DataFrame,
    rsi_period: int = 14,
    lb_left: int = 5,
    lb_right: int = 5,
    range_lower: int = 5,
    range_upper: int = 60,
    lookback: int = 2,
) -> tuple[list[ChartDivergence], pd.Series, dict[int, int], dict[int, int]]:
    """
    Enhanced RSI divergence detection with lookback parameter.
    Compares each pivot with previous N pivots (not just consecutive).

    Returns:
        (signals, rsi_series, pivot_lows_dict, pivot_highs_dict)
    """
    d = df.copy()
    d.columns = [c.lower() for c in d.columns]

    if len(d) < rsi_period + lb_left + lb_right + 10:
        return [], pd.Series(dtype=float), {}, {}

    rsi = calc_rsi(d["close"], rsi_period)
    pl = find_pivots_indexed(rsi, lb_left, lb_right, "low")
    ph = find_pivots_indexed(rsi, lb_left, lb_right, "high")
    sigs: list[ChartDivergence] = []

    # Bullish divergences (pivot low comparisons)
    spl = sorted(pl.items())
    for i in range(1, len(spl)):
        cc, cp = spl[i]
        for back in range(1, min(lookback + 1, i + 1)):
            pc, pp = spl[i - back]
            gap = cc - pc
            if gap < range_lower:
                continue
            if gap > range_upper:
                break
            c_p, p_p = d["low"].iloc[cp], d["low"].iloc[pp]
            c_r, p_r = rsi.iloc[cp], rsi.iloc[pp]
            if c_p < p_p and c_r > p_r:
                sigs.append(ChartDivergence(
                    "regular_bullish", "Bull", cp, pp, c_p, c_r, p_p, p_r,
                ))
                break
            elif c_p > p_p and c_r < p_r:
                sigs.append(ChartDivergence(
                    "hidden_bullish", "H.Bull", cp, pp, c_p, c_r, p_p, p_r,
                ))
                break

    # Bearish divergences (pivot high comparisons)
    sph = sorted(ph.items())
    for i in range(1, len(sph)):
        cc, cp = sph[i]
        for back in range(1, min(lookback + 1, i + 1)):
            pc, pp = sph[i - back]
            gap = cc - pc
            if gap < range_lower:
                continue
            if gap > range_upper:
                break
            c_p, p_p = d["high"].iloc[cp], d["high"].iloc[pp]
            c_r, p_r = rsi.iloc[cp], rsi.iloc[pp]
            if c_p > p_p and c_r < p_r:
                sigs.append(ChartDivergence(
                    "regular_bearish", "Bear", cp, pp, c_p, c_r, p_p, p_r,
                ))
                break
            elif c_p < p_p and c_r > p_r:
                sigs.append(ChartDivergence(
                    "hidden_bearish", "H.Bear", cp, pp, c_p, c_r, p_p, p_r,
                ))
                break

    sigs.sort(key=lambda s: s.idx)
    return sigs, rsi, pl, ph
