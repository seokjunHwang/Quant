"""
Converted from Pine Script: TSR.pine (Trend Lines, Supports and Resistances)
Original author: ismailcarlik
Converted at: 2026-02-25

Detects pivot points on price (high/low), then draws:
  - Trend lines connecting pivot pairs (uptrend from low pivots, downtrend from high pivots)
  - Support/Resistance horizontal zones from pivot points
"""

from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
import pandas as pd

METADATA = {
    "name": "TSR (Trend Lines, Supports, Resistances)",
    "category": "overlay",
    "default_params": {
        "pvt_length": 5,
        "tl_points_to_check": 3,
        "tl_max_violation": 0,
        "tl_except_bars": 3,
        "sr_points_to_check": 3,
        "sr_max_violation": 0,
        "sr_except_bars": 3,
    },
    "description": "피봇 기반 추세선 + 지지/저항 존 자동 탐지",
}


# ============================================================
# Dataclasses
# ============================================================

@dataclass
class PivotPoint:
    """A pivot point on the price chart."""
    idx: int       # bar index of the pivot
    price: float   # high or low price at the pivot


@dataclass
class TsrTrendLine:
    """A trend line connecting two pivot points."""
    start_idx: int
    start_price: float
    end_idx: int
    end_price: float
    direction: str       # "up" or "down"
    is_violated: bool = False
    ext_idx: int | None = None    # extension endpoint bar index
    ext_price: float | None = None


@dataclass
class TsrSrZone:
    """A support or resistance zone."""
    zone_type: str    # "support" or "resistance"
    start_idx: int    # pivot bar index
    end_idx: int      # last bar index
    top: float
    bottom: float
    price: float      # the level price


@dataclass
class TsrPivotMarker:
    """A pivot marker for chart display."""
    idx: int
    price: float
    pivot_type: str   # "high" or "low"


@dataclass
class TsrResult:
    """Complete TSR indicator output."""
    trend_lines: list[TsrTrendLine] = field(default_factory=list)
    sr_zones: list[TsrSrZone] = field(default_factory=list)
    pivot_markers: list[TsrPivotMarker] = field(default_factory=list)


# ============================================================
# Core functions
# ============================================================

def find_price_pivots(
    series: pd.Series, lb_left: int, lb_right: int, mode: str,
) -> list[PivotPoint]:
    """
    Find pivot highs or lows on a price series.
    Matches Pine: ta.pivothigh(pvtLength, pvtLength) / ta.pivotlow(pvtLength, pvtLength)

    Returns list of PivotPoint sorted by index (oldest first).
    """
    values = series.values
    pivots: list[PivotPoint] = []

    for i in range(lb_left, len(values) - lb_right):
        val = values[i]
        if np.isnan(val):
            continue
        left = values[i - lb_left:i]
        right = values[i + 1:i + 1 + lb_right]
        if len(left) < lb_left or len(right) < lb_right:
            continue
        if np.any(np.isnan(left)) or np.any(np.isnan(right)):
            continue

        if mode == "high":
            if np.all(val >= left) and np.all(val > right):
                pivots.append(PivotPoint(idx=i, price=float(val)))
        else:  # low
            if np.all(val <= left) and np.all(val < right):
                pivots.append(PivotPoint(idx=i, price=float(val)))

    return pivots


def line_get_price(x1: int, y1: float, x2: int, y2: float, target_x: int) -> float:
    """Linear interpolation/extrapolation: get y at target_x given two points."""
    if x2 == x1:
        return y1
    slope = (y2 - y1) / (x2 - x1)
    return y1 + slope * (target_x - x1)


def count_violations_uptrend(
    df: pd.DataFrame, start_idx: int, start_price: float,
    end_idx: int, end_price: float, last_bar: int, except_bars: int,
) -> int:
    """Count bars where low < trend line price (uptrend violation)."""
    count = 0
    # Check from start_idx to last_bar - except_bars
    check_end = last_bar - except_bars
    for i in range(start_idx, check_end + 1):
        if i < 0 or i >= len(df):
            continue
        tl_price = line_get_price(start_idx, start_price, end_idx, end_price, i)
        if df["low"].iloc[i] < tl_price:
            count += 1
    return count


def count_violations_downtrend(
    df: pd.DataFrame, start_idx: int, start_price: float,
    end_idx: int, end_price: float, last_bar: int, except_bars: int,
) -> int:
    """Count bars where high > trend line price (downtrend violation)."""
    count = 0
    check_end = last_bar - except_bars
    for i in range(start_idx, check_end + 1):
        if i < 0 or i >= len(df):
            continue
        tl_price = line_get_price(start_idx, start_price, end_idx, end_price, i)
        if df["high"].iloc[i] > tl_price:
            count += 1
    return count


def check_support_violation(
    df: pd.DataFrame, pivot_idx: int, pivot_price: float,
    last_bar: int, except_bars: int,
) -> int:
    """Count bars where low < support price."""
    count = 0
    check_end = last_bar - except_bars
    for i in range(pivot_idx, check_end + 1):
        if i < 0 or i >= len(df):
            continue
        if df["low"].iloc[i] < pivot_price:
            count += 1
    return count


def check_resistance_violation(
    df: pd.DataFrame, pivot_idx: int, pivot_price: float,
    last_bar: int, except_bars: int,
) -> int:
    """Count bars where high > resistance price."""
    count = 0
    check_end = last_bar - except_bars
    for i in range(pivot_idx, check_end + 1):
        if i < 0 or i >= len(df):
            continue
        if df["high"].iloc[i] > pivot_price:
            count += 1
    return count


# ============================================================
# Main computation
# ============================================================

def compute_tsr(
    df: pd.DataFrame,
    pvt_length: int = 5,
    tl_points_to_check: int = 3,
    tl_max_violation: int = 0,
    tl_except_bars: int = 3,
    sr_points_to_check: int = 3,
    sr_max_violation: int = 0,
    sr_except_bars: int = 3,
) -> TsrResult:
    """
    Compute TSR indicator: trend lines + support/resistance zones.

    Pine Script port of TSR.pine by ismailcarlik.
    """
    d = df.copy()
    d.columns = [c.lower() for c in d.columns]

    if len(d) < pvt_length * 2 + 10:
        return TsrResult()

    last_bar = len(d) - 1

    # --- Pivot detection (on price, not RSI) ---
    high_pivots = find_price_pivots(d["high"], pvt_length, pvt_length, "high")
    low_pivots = find_price_pivots(d["low"], pvt_length, pvt_length, "low")

    # Pine stores most recent first (unshift), we need to reverse for "most recent N"
    high_pivots_recent = list(reversed(high_pivots))  # index 0 = most recent
    low_pivots_recent = list(reversed(low_pivots))

    result = TsrResult()

    # Pivot markers
    for p in high_pivots:
        result.pivot_markers.append(TsrPivotMarker(idx=p.idx, price=p.price, pivot_type="high"))
    for p in low_pivots:
        result.pivot_markers.append(TsrPivotMarker(idx=p.idx, price=p.price, pivot_type="low"))

    # --- Trend Lines ---
    # Pine: lowPivots.slice(0, tlPointsToCheck).reversed() → take most recent N, oldest first
    tl_low_points = low_pivots_recent[:tl_points_to_check]
    tl_low_points_ordered = list(reversed(tl_low_points))  # oldest first

    tl_high_points = high_pivots_recent[:tl_points_to_check]
    tl_high_points_ordered = list(reversed(tl_high_points))

    # Uptrends: from low pivot pairs where first < second (ascending lows)
    if len(tl_low_points_ordered) >= 2:
        for p1, p2 in combinations(tl_low_points_ordered, 2):
            if p1.price < p2.price:  # ascending → uptrend
                ext_price = line_get_price(p1.idx, p1.price, p2.idx, p2.price, last_bar)
                violations = count_violations_uptrend(
                    d, p1.idx, p1.price, p2.idx, p2.price, last_bar, tl_except_bars,
                )
                is_violated = violations > tl_max_violation
                result.trend_lines.append(TsrTrendLine(
                    start_idx=p1.idx, start_price=p1.price,
                    end_idx=p2.idx, end_price=p2.price,
                    direction="up", is_violated=is_violated,
                    ext_idx=last_bar, ext_price=ext_price,
                ))

    # Downtrends: from high pivot pairs where first > second (descending highs)
    if len(tl_high_points_ordered) >= 2:
        for p1, p2 in combinations(tl_high_points_ordered, 2):
            if p1.price > p2.price:  # descending → downtrend
                ext_price = line_get_price(p1.idx, p1.price, p2.idx, p2.price, last_bar)
                violations = count_violations_downtrend(
                    d, p1.idx, p1.price, p2.idx, p2.price, last_bar, tl_except_bars,
                )
                is_violated = violations > tl_max_violation
                result.trend_lines.append(TsrTrendLine(
                    start_idx=p1.idx, start_price=p1.price,
                    end_idx=p2.idx, end_price=p2.price,
                    direction="down", is_violated=is_violated,
                    ext_idx=last_bar, ext_price=ext_price,
                ))

    # --- Support & Resistance Zones ---
    # Pine: walk through most recent pivots, find ones that are local extremes
    # Support: lowPivots[lIndex].price < lowPivots[lIndex + 1].price (current is lower than next older)
    if len(low_pivots_recent) >= 2:
        s_count = 0
        l_idx = 0
        while s_count < sr_points_to_check and l_idx + 1 < len(low_pivots_recent):
            curr = low_pivots_recent[l_idx]
            nxt = low_pivots_recent[l_idx + 1]
            if curr.price < nxt.price:  # current is a local low
                violations = check_support_violation(
                    d, curr.idx, curr.price, last_bar, sr_except_bars,
                )
                if violations <= sr_max_violation:
                    # Box: from pivot bar to last bar
                    # top = min(open, close) at pivot bar, bottom = low at pivot bar
                    o = d["open"].iloc[curr.idx]
                    c = d["close"].iloc[curr.idx]
                    box_top = min(o, c)
                    box_bottom = curr.price
                    result.sr_zones.append(TsrSrZone(
                        zone_type="support",
                        start_idx=curr.idx, end_idx=last_bar,
                        top=box_top, bottom=box_bottom,
                        price=curr.price,
                    ))
                s_count += 1
            l_idx += 1

    # Resistance: highPivots[hIndex].price > highPivots[hIndex + 1].price
    if len(high_pivots_recent) >= 2:
        r_count = 0
        h_idx = 0
        while r_count < sr_points_to_check and h_idx + 1 < len(high_pivots_recent):
            curr = high_pivots_recent[h_idx]
            nxt = high_pivots_recent[h_idx + 1]
            if curr.price > nxt.price:  # current is a local high
                violations = check_resistance_violation(
                    d, curr.idx, curr.price, last_bar, sr_except_bars,
                )
                if violations <= sr_max_violation:
                    o = d["open"].iloc[curr.idx]
                    c = d["close"].iloc[curr.idx]
                    box_top = curr.price
                    box_bottom = max(o, c)
                    result.sr_zones.append(TsrSrZone(
                        zone_type="resistance",
                        start_idx=curr.idx, end_idx=last_bar,
                        top=box_top, bottom=box_bottom,
                        price=curr.price,
                    ))
                r_count += 1
            h_idx += 1

    return result
