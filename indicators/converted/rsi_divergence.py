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
        "lookback": 1,
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
                        results.append(RawDivergence(
                            signal_type="regular_bullish", signal_label="Bull",
                            bar_index=i, timestamp=pd.Timestamp(df.index[i]),
                            price=float(df["close"].iloc[i - lb_right]),
                            rsi=float(osc.iloc[i - lb_right]),
                        ))
                    if curr_price > prev_price and curr_osc < prev_osc:
                        results.append(RawDivergence(
                            signal_type="hidden_bullish", signal_label="H Bull",
                            bar_index=i, timestamp=pd.Timestamp(df.index[i]),
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
                        results.append(RawDivergence(
                            signal_type="regular_bearish", signal_label="Bear",
                            bar_index=i, timestamp=pd.Timestamp(df.index[i]),
                            price=float(df["close"].iloc[i - lb_right]),
                            rsi=float(osc.iloc[i - lb_right]),
                        ))
                    if curr_price < prev_price and curr_osc > prev_osc:
                        results.append(RawDivergence(
                            signal_type="hidden_bearish", signal_label="H Bear",
                            bar_index=i, timestamp=pd.Timestamp(df.index[i]),
                            price=float(df["close"].iloc[i - lb_right]),
                            rsi=float(osc.iloc[i - lb_right]),
                        ))

    results.sort(key=lambda x: x.timestamp, reverse=True)
    return results


# ============================================================
# v2: Pine Script 1:1 port (for chart API)
# ============================================================

def detect_divergences_v2(
    df: pd.DataFrame,
    rsi_period: int = 14,
    lb_left: int = 5,
    lb_right: int = 5,
    range_lower: int = 5,
    range_upper: int = 60,
    lookback: int = 1,
) -> tuple[list[ChartDivergence], pd.Series, dict[int, int], dict[int, int]]:
    """
    RSI divergence detection — 1:1 port of Pine Script logic.

    Pine Script key lines:
        plFound = na(ta.pivotlow(osc, lbL, lbR)) ? false : true
        inRangePl = _inRange(plFound[1])          // barssince(plFound shifted by 1)
        oscHL = osc[lbR] > ta.valuewhen(plFound, osc[lbR], 1) and inRangePl
        priceLL = low[lbR] < ta.valuewhen(plFound, low[lbR], 1)
        bullCondAlert = priceLL and oscHL and plFound

    Returns:
        (signals, rsi_series, pivot_lows_dict, pivot_highs_dict)
    """
    d = df.copy()
    d.columns = [c.lower() for c in d.columns]

    if len(d) < rsi_period + lb_left + lb_right + 10:
        return [], pd.Series(dtype=float), {}, {}

    osc = calc_rsi(d["close"], rsi_period)

    # --- Pivot detection (same as Pine: ta.pivotlow/high on RSI) ---
    pl_found = find_pivot_lows(osc, lb_left, lb_right)
    ph_found = find_pivot_highs(osc, lb_left, lb_right)

    # Build pivot dicts for chart display: {confirm_bar: pivot_bar}
    pl_dict: dict[int, int] = {}
    ph_dict: dict[int, int] = {}
    for i in range(len(d)):
        if pl_found.iloc[i]:
            pl_dict[i] = i - lb_right
        if ph_found.iloc[i]:
            ph_dict[i] = i - lb_right

    # --- Pine: osc[lbR] and low[lbR] / high[lbR] at confirm bar ---
    # At confirm bar i, the actual pivot bar is i - lb_right
    # Pine's osc[lbR] at bar i = osc at bar i - lbR = osc at pivot bar

    # --- Pine: _inRange(plFound[1]) ---
    # barssince(plFound shifted by 1), then rangeLower <= bars <= rangeUpper
    bs_pl = barssince(pl_found.shift(1, fill_value=False))
    bs_ph = barssince(ph_found.shift(1, fill_value=False))

    # --- Pine: valuewhen(plFound, osc[lbR], N) ---
    # We need osc and price values at pivot bars, indexed at confirm bars
    osc_at_pl = pd.Series(np.nan, index=d.index)
    price_at_pl = pd.Series(np.nan, index=d.index)
    osc_at_ph = pd.Series(np.nan, index=d.index)
    price_at_ph = pd.Series(np.nan, index=d.index)

    for i in range(lb_right, len(d)):
        if pl_found.iloc[i]:
            osc_at_pl.iloc[i] = osc.iloc[i - lb_right]
            price_at_pl.iloc[i] = d["low"].iloc[i - lb_right]
        if ph_found.iloc[i]:
            osc_at_ph.iloc[i] = osc.iloc[i - lb_right]
            price_at_ph.iloc[i] = d["high"].iloc[i - lb_right]

    # Track pivot history for prev_idx lookups (needed for line drawing)
    # pl_history[n] = list of (confirm_bar, pivot_bar) in order
    sigs: list[ChartDivergence] = []

    # --- Bullish divergences ---
    pl_history: list[tuple[int, int]] = []  # (confirm_bar, pivot_bar)

    for i in range(len(d)):
        if not pl_found.iloc[i]:
            continue
        pivot_bar = i - lb_right

        # Pine: _inRange(plFound[1]) — check distance to PREVIOUS pivot
        in_range = (
            not np.isnan(bs_pl.iloc[i])
            and range_lower <= bs_pl.iloc[i] <= range_upper
        )

        if in_range and len(pl_history) >= 1:
            # Compare with previous N pivots (lookback parameter)
            for back in range(1, min(lookback + 1, len(pl_history) + 1)):
                prev_confirm, prev_pivot = pl_history[-back]

                # Re-check range for non-consecutive pivots
                bars_gap = i - prev_confirm - 1  # matches Pine's plFound[1] shift
                if bars_gap < range_lower or bars_gap > range_upper:
                    continue

                curr_osc = osc.iloc[pivot_bar]
                prev_osc = osc.iloc[prev_pivot]
                curr_price = d["low"].iloc[pivot_bar]
                prev_price = d["low"].iloc[prev_pivot]

                # Pine: priceLL and oscHL (Regular Bullish)
                if curr_price < prev_price and curr_osc > prev_osc:
                    sigs.append(ChartDivergence(
                        "regular_bullish", "Bull",
                        pivot_bar, prev_pivot,
                        curr_price, curr_osc, prev_price, prev_osc,
                    ))
                    break
                # Pine: priceHL and oscLL (Hidden Bullish)
                elif curr_price > prev_price and curr_osc < prev_osc:
                    sigs.append(ChartDivergence(
                        "hidden_bullish", "H.Bull",
                        pivot_bar, prev_pivot,
                        curr_price, curr_osc, prev_price, prev_osc,
                    ))
                    break

        pl_history.append((i, pivot_bar))

    # --- Bearish divergences ---
    ph_history: list[tuple[int, int]] = []

    for i in range(len(d)):
        if not ph_found.iloc[i]:
            continue
        pivot_bar = i - lb_right

        in_range = (
            not np.isnan(bs_ph.iloc[i])
            and range_lower <= bs_ph.iloc[i] <= range_upper
        )

        if in_range and len(ph_history) >= 1:
            for back in range(1, min(lookback + 1, len(ph_history) + 1)):
                prev_confirm, prev_pivot = ph_history[-back]

                bars_gap = i - prev_confirm - 1
                if bars_gap < range_lower or bars_gap > range_upper:
                    continue

                curr_osc = osc.iloc[pivot_bar]
                prev_osc = osc.iloc[prev_pivot]
                curr_price = d["high"].iloc[pivot_bar]
                prev_price = d["high"].iloc[prev_pivot]

                # Pine: priceHH and oscLH (Regular Bearish)
                if curr_price > prev_price and curr_osc < prev_osc:
                    sigs.append(ChartDivergence(
                        "regular_bearish", "Bear",
                        pivot_bar, prev_pivot,
                        curr_price, curr_osc, prev_price, prev_osc,
                    ))
                    break
                # Pine: priceLH and oscHH (Hidden Bearish)
                elif curr_price < prev_price and curr_osc > prev_osc:
                    sigs.append(ChartDivergence(
                        "hidden_bearish", "H.Bear",
                        pivot_bar, prev_pivot,
                        curr_price, curr_osc, prev_price, prev_osc,
                    ))
                    break

        ph_history.append((i, pivot_bar))

    sigs.sort(key=lambda s: s.idx)
    return sigs, osc, pl_dict, ph_dict
