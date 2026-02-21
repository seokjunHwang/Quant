"""
Auto-converted from Pine Script: SR_breaks_n_retests.pine
Original: Support and Resistance (High Volume Boxes) [ChartPrime]
Indicator type: Information (no buy/sell signals — provides S/R levels, breakouts, retests)

Outputs:
  - support_level / resistance_level: Current S/R price levels
  - support_bottom / resistance_top: S/R zone boundaries (ATR-based width)
  - sup_holds / res_holds: Boolean markers when S/R holds
  - brekout_res / brekout_sup: Boolean markers when S/R breaks
  - res_is_sup / sup_is_res: Role reversal state
  - markers: List of dicts for chart visualization
"""
import pandas as pd
import numpy as np

METADATA = {
    "name": "SR Breaks and Retests",
    "category": "pattern",
    "default_params": {"lookback_period": 20, "vol_len": 2, "box_width": 1.0},
    "description": "High-volume pivot 기반 지지/저항 박스 + 돌파/리테스트 감지",
    "has_signals": False,  # Information-only indicator
}


def _pivot_high(series: pd.Series, left: int, right: int) -> pd.Series:
    """Detect pivot highs: highest point within left+right bars."""
    result = pd.Series(np.nan, index=series.index)
    for i in range(left, len(series) - right):
        window = series.iloc[i - left: i + right + 1]
        if series.iloc[i] == window.max():
            result.iloc[i] = series.iloc[i]
    return result


def _pivot_low(series: pd.Series, left: int, right: int) -> pd.Series:
    """Detect pivot lows: lowest point within left+right bars."""
    result = pd.Series(np.nan, index=series.index)
    for i in range(left, len(series) - right):
        window = series.iloc[i - left: i + right + 1]
        if series.iloc[i] == window.min():
            result.iloc[i] = series.iloc[i]
    return result


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 200) -> pd.Series:
    """Average True Range."""
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=length, min_periods=1).mean()


def _crossover(a: pd.Series, b) -> pd.Series:
    """a crosses above b."""
    if isinstance(b, (int, float)):
        b = pd.Series(b, index=a.index)
    return (a > b) & (a.shift(1) <= b.shift(1))


def _crossunder(a: pd.Series, b) -> pd.Series:
    """a crosses below b."""
    if isinstance(b, (int, float)):
        b = pd.Series(b, index=a.index)
    return (a < b) & (a.shift(1) >= b.shift(1))


def generate_indicator_data(
    df: pd.DataFrame,
    lookback_period: int = 20,
    vol_len: int = 2,
    box_width: float = 1.0,
) -> pd.DataFrame:
    """Compute S/R levels, breakouts, and retests.

    Returns DataFrame with additional columns for S/R data and markers.
    """
    result = df.copy()
    n = len(result)

    # ── Delta Volume ──
    delta_vol = pd.Series(0.0, index=result.index)
    is_buy = result["close"] > result["open"]
    delta_vol[is_buy] = result["volume"][is_buy]
    delta_vol[~is_buy] = -result["volume"][~is_buy]
    result["delta_vol"] = delta_vol

    vol_scaled = delta_vol / 2.5
    vol_hi = vol_scaled.rolling(window=vol_len, min_periods=1).max()
    vol_lo = vol_scaled.rolling(window=vol_len, min_periods=1).min()

    # ── Pivot Points ──
    # Raw pivots mark the actual pivot bar
    pivot_high_raw = _pivot_high(result["close"], lookback_period, lookback_period)
    pivot_low_raw = _pivot_low(result["close"], lookback_period, lookback_period)

    # Pine Script's ta.pivothigh/low detect pivots with a `right`-bar delay.
    # Volume check in Pine happens at the DETECTION bar (current), not the pivot bar.
    # Shift forward by lookback_period to match this behavior.
    pivot_high_detected = pivot_high_raw.shift(lookback_period)
    pivot_low_detected = pivot_low_raw.shift(lookback_period)

    # ── ATR for box width ──
    atr = _atr(result["high"], result["low"], result["close"], 200)
    withd = atr * box_width

    # ── Track S/R levels ──
    support_level = pd.Series(np.nan, index=result.index)
    support_bottom = pd.Series(np.nan, index=result.index)
    resistance_level = pd.Series(np.nan, index=result.index)
    resistance_top = pd.Series(np.nan, index=result.index)

    # S/R box tracking
    boxes = []  # List of {type, start_idx, level, boundary, vol}
    cur_sup = np.nan
    cur_sup_bottom = np.nan
    cur_res = np.nan
    cur_res_top = np.nan

    for i in range(n):
        # Support: pivot low detected now + positive volume at detection bar
        if not np.isnan(pivot_low_detected.iloc[i]) and delta_vol.iloc[i] > vol_hi.iloc[i]:
            cur_sup = pivot_low_detected.iloc[i]
            cur_sup_bottom = cur_sup - withd.iloc[i]
            pivot_bar = max(0, i - lookback_period)
            boxes.append({
                "type": "support",
                "start_bar": max(0, pivot_bar - lookback_period),
                "end_bar": i,
                "top": round(float(cur_sup), 2),
                "bottom": round(float(cur_sup_bottom), 2),
                "vol": round(float(delta_vol.iloc[i]), 2),
            })

        # Resistance: pivot high detected now + negative volume at detection bar
        if not np.isnan(pivot_high_detected.iloc[i]) and delta_vol.iloc[i] < vol_lo.iloc[i]:
            cur_res = pivot_high_detected.iloc[i]
            cur_res_top = cur_res + withd.iloc[i]
            pivot_bar = max(0, i - lookback_period)
            boxes.append({
                "type": "resistance",
                "start_bar": max(0, pivot_bar - lookback_period),
                "end_bar": i,
                "top": round(float(cur_res_top), 2),
                "bottom": round(float(cur_res), 2),
                "vol": round(float(delta_vol.iloc[i]), 2),
            })

        support_level.iloc[i] = cur_sup
        support_bottom.iloc[i] = cur_sup_bottom
        resistance_level.iloc[i] = cur_res
        resistance_top.iloc[i] = cur_res_top

    result["support_level"] = support_level
    result["support_bottom"] = support_bottom
    result["resistance_level"] = resistance_level
    result["resistance_top"] = resistance_top

    # ── Breakout / Hold detection ──
    result["brekout_res"] = _crossover(result["low"], resistance_top)
    result["res_holds"] = _crossunder(result["high"], resistance_level)
    result["sup_holds"] = _crossover(result["low"], support_level)
    result["brekout_sup"] = _crossunder(result["high"], support_bottom)

    # ── Role reversal tracking ──
    res_is_sup = pd.Series(False, index=result.index, dtype=bool)
    sup_is_res = pd.Series(False, index=result.index, dtype=bool)
    _ris = False
    _sir = False
    for i in range(n):
        if result["brekout_res"].iloc[i]:
            _ris = True
        elif result["res_holds"].iloc[i]:
            _ris = False
        if result["brekout_sup"].iloc[i]:
            _sir = True
        elif result["sup_holds"].iloc[i]:
            _sir = False
        res_is_sup.iloc[i] = _ris
        sup_is_res.iloc[i] = _sir

    result["res_is_sup"] = res_is_sup
    result["sup_is_res"] = sup_is_res

    # ── Generate markers for chart display ──
    # Pine Script uses offset = -1 on all plotchar calls → marker appears 1 bar before signal
    markers = []
    dates = result.index

    for i in range(2, n):  # start at 2 so i-1 is valid for offset
        # offset = -1: place marker at previous bar's timestamp
        ts_prev = int(dates[i - 1].timestamp()) if hasattr(dates[i - 1], "timestamp") else 0

        # Support holds → green diamond below bar
        if result["sup_holds"].iloc[i]:
            markers.append({
                "time": ts_prev, "position": "belowBar", "color": "#20ca26",
                "shape": "circle", "text": "◆",
            })

        # Resistance holds → red diamond above bar
        if result["res_holds"].iloc[i]:
            markers.append({
                "time": ts_prev, "position": "aboveBar", "color": "#e92929",
                "shape": "circle", "text": "◆",
            })

        # Resistance breakout (role reversal: R→S hold)
        if result["brekout_res"].iloc[i]:
            if res_is_sup.iloc[i - 1]:
                markers.append({
                    "time": ts_prev, "position": "belowBar", "color": "#20ca26",
                    "shape": "circle", "text": "◆",
                })
            else:
                # Break Res label at bar_index[1] (previous bar)
                markers.append({
                    "time": ts_prev, "position": "belowBar", "color": "#2b6d2d",
                    "shape": "arrowUp", "text": "Break Res",
                })

        # Support breakdown (role reversal: S→R hold)
        if result["brekout_sup"].iloc[i]:
            if sup_is_res.iloc[i - 1]:
                markers.append({
                    "time": ts_prev, "position": "aboveBar", "color": "#e92929",
                    "shape": "circle", "text": "◆",
                })
            else:
                markers.append({
                    "time": ts_prev, "position": "aboveBar", "color": "#7e1e1e",
                    "shape": "arrowDown", "text": "Break Sup",
                })

    result.attrs["markers"] = markers
    result.attrs["boxes"] = boxes

    return result


def get_chart_data(df: pd.DataFrame, **params) -> dict:
    """Compute indicator and return structured data for frontend chart.

    Returns:
        {
            "markers": [...],   # Chart markers (diamonds, arrows)
            "levels": {...},    # Current S/R levels
            "boxes": [...],     # S/R zone boxes with timestamps
        }
    """
    result = generate_indicator_data(df, **params)
    markers = result.attrs.get("markers", [])
    raw_boxes = result.attrs.get("boxes", [])
    dates = result.index
    n = len(result)

    def _ts(i: int) -> int:
        idx = dates[min(i, n - 1)]
        return int(idx.timestamp()) if hasattr(idx, "timestamp") else 0

    last_ts = _ts(n - 1)

    # Current S/R levels (last non-NaN values)
    last_sup = result["support_level"].dropna().iloc[-1] if result["support_level"].notna().any() else None
    last_sup_bottom = result["support_bottom"].dropna().iloc[-1] if result["support_bottom"].notna().any() else None
    last_res = result["resistance_level"].dropna().iloc[-1] if result["resistance_level"].notna().any() else None
    last_res_top = result["resistance_top"].dropna().iloc[-1] if result["resistance_top"].notna().any() else None

    # Convert boxes to have timestamps + extend each box until next box of same type
    sup_boxes = [b for b in raw_boxes if b["type"] == "support"]
    res_boxes = [b for b in raw_boxes if b["type"] == "resistance"]

    chart_boxes = []
    for group in [sup_boxes, res_boxes]:
        for idx_b, box in enumerate(group):
            start_time = _ts(box["start_bar"])
            # Box extends until the next box of same type starts, or to the last bar
            if idx_b < len(group) - 1:
                end_time = _ts(group[idx_b + 1]["start_bar"])
            else:
                # Latest box extends to the right edge
                end_time = last_ts + 86400  # +1 day to extend past last bar
            chart_boxes.append({
                "type": box["type"],
                "start_time": start_time,
                "end_time": end_time,
                "top": box["top"],
                "bottom": box["bottom"],
                "vol": box["vol"],
                "active": idx_b == len(group) - 1,  # latest box of this type
            })

    return {
        "markers": markers,
        "levels": {
            "support": round(float(last_sup), 2) if last_sup is not None else None,
            "support_bottom": round(float(last_sup_bottom), 2) if last_sup_bottom is not None else None,
            "resistance": round(float(last_res), 2) if last_res is not None else None,
            "resistance_top": round(float(last_res_top), 2) if last_res_top is not None else None,
        },
        "boxes": chart_boxes,
    }
