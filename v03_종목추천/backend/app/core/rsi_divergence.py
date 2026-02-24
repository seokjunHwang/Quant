"""
RSI Divergence — thin wrapper that imports from indicators/converted/rsi_divergence.py
전략 로직 원본: /workspace/Quant/indicators/converted/rsi_divergence.py
"""

import sys
from pathlib import Path

# indicators/converted/ 를 import 경로에 추가
_INDICATORS_DIR = Path(__file__).resolve().parents[4] / "indicators" / "converted"
_QUANT_ROOT = str(_INDICATORS_DIR.parent.parent)  # /workspace/Quant
if _QUANT_ROOT not in sys.path:
    sys.path.insert(0, _QUANT_ROOT)

# 전략 로직 전부 re-export
from indicators.converted.rsi_divergence import (  # noqa: E402
    RawDivergence,
    ChartDivergence,
    calc_rsi,
    find_pivot_lows,
    find_pivot_highs,
    find_pivots_indexed,
    valuewhen,
    barssince,
    detect_divergences as _detect_divergences_raw,
    detect_divergences_v2,
)

from app.config import settings


def detect_divergences(
    df,
    rsi_period=None,
    lb_left=None,
    lb_right=None,
    range_lower=None,
    range_upper=None,
):
    """Wrapper that injects default params from app settings."""
    return _detect_divergences_raw(
        df,
        rsi_period=rsi_period or settings.RSI_PERIOD,
        lb_left=lb_left or settings.PIVOT_LOOKBACK_LEFT,
        lb_right=lb_right or settings.PIVOT_LOOKBACK_RIGHT,
        range_lower=range_lower or settings.RANGE_LOWER,
        range_upper=range_upper or settings.RANGE_UPPER,
    )


__all__ = [
    "RawDivergence",
    "ChartDivergence",
    "calc_rsi",
    "find_pivot_lows",
    "find_pivot_highs",
    "find_pivots_indexed",
    "valuewhen",
    "barssince",
    "detect_divergences",
    "detect_divergences_v2",
]
