"""
TSR (Trend Lines, Supports, Resistances) — thin wrapper
전략 로직 원본: /workspace/Quant/indicators/converted/tsr.py
"""

import sys
from pathlib import Path

# indicators/converted/ 를 import 경로에 추가
_QUANT_ROOT = str(Path(__file__).resolve().parents[4])  # /workspace/Quant
if _QUANT_ROOT not in sys.path:
    sys.path.insert(0, _QUANT_ROOT)

from indicators.converted.tsr import (  # noqa: E402
    PivotPoint,
    TsrTrendLine,
    TsrSrZone,
    TsrPivotMarker,
    TsrResult,
    compute_tsr,
)

__all__ = [
    "PivotPoint",
    "TsrTrendLine",
    "TsrSrZone",
    "TsrPivotMarker",
    "TsrResult",
    "compute_tsr",
]
