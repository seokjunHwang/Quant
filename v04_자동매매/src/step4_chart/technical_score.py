"""
Step 4: 기술적 지표 스코어링.

v03의 RSI 다이버전스 엔진을 재사용하고,
추가로 VWAP, 볼린저밴드, SMA 등 기술 지표를 계산하여 점수화.
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Import RSI divergence engine from shared indicators
_INDICATORS_DIR = Path(__file__).parent.parent.parent.parent / "indicators"
if str(_INDICATORS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_INDICATORS_DIR.parent))

try:
    from indicators.converted.rsi_divergence import compute_signals as compute_rsi_signals
except ImportError:
    logger.warning("Could not import RSI divergence engine from v03")
    compute_rsi_signals = None


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI 계산 (Wilder's smoothing)."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.inf)
    return 100 - (100 / (1 + rs))


def calc_vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP 계산 (일중 데이터 기준)."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cum_tp_vol = (typical_price * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum()
    return cum_tp_vol / cum_vol.replace(0, np.nan)


def calc_bollinger(df: pd.DataFrame, period: int = 20, std_mult: float = 2.0) -> dict:
    """볼린저밴드 계산."""
    sma = df["close"].rolling(period).mean()
    std = df["close"].rolling(period).std()
    return {
        "upper": sma + std_mult * std,
        "middle": sma,
        "lower": sma - std_mult * std,
        "bandwidth": ((sma + std_mult * std) - (sma - std_mult * std)) / sma * 100,
    }


def calc_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def score_technical(df: pd.DataFrame) -> dict:
    """
    기술적 지표 점수 계산 (0~20점).

    지표별 점수:
    - VWAP 위치: 현재가 > VWAP → +2
    - RSI 위치: 40~60 (눌림목) → +2
    - 볼린저밴드 수축 후 확장: +3
    - 52주 고점 돌파 시도 (95% 이내): +2
    - 20 SMA > 60 SMA (상승 추세): +2
    """
    if df is None or len(df) < 60:
        return {"total": 0, "details": {}}

    score = 0
    details = {}
    close = df["close"]
    latest = close.iloc[-1]

    # 1. VWAP position (+2)
    vwap = calc_vwap(df)
    if not vwap.empty and not np.isnan(vwap.iloc[-1]):
        above_vwap = latest > vwap.iloc[-1]
        if above_vwap:
            score += 2
        details["vwap"] = {"above": above_vwap, "score": 2 if above_vwap else 0}

    # 2. RSI sweet spot 40-60 (+2)
    rsi = calc_rsi(close)
    rsi_val = rsi.iloc[-1] if not rsi.empty else 50
    in_sweet_spot = 40 <= rsi_val <= 60
    if in_sweet_spot:
        score += 2
    details["rsi"] = {"value": round(rsi_val, 1), "sweet_spot": in_sweet_spot, "score": 2 if in_sweet_spot else 0}

    # 3. Bollinger Band squeeze → expansion (+3)
    bb = calc_bollinger(df)
    if len(bb["bandwidth"].dropna()) >= 20:
        bw = bb["bandwidth"].dropna()
        recent_bw = bw.iloc[-1]
        avg_bw = bw.iloc[-20:].mean()
        prev_bw = bw.iloc[-5:-1].mean()
        # Squeeze: prev bandwidth < avg, current expanding
        is_expanding = recent_bw > prev_bw and prev_bw < avg_bw
        if is_expanding:
            score += 3
        details["bollinger"] = {
            "expanding": is_expanding,
            "bandwidth": round(recent_bw, 2),
            "score": 3 if is_expanding else 0,
        }

    # 4. Near 52-week high (+2)
    high_52w = close.rolling(252).max().iloc[-1] if len(close) >= 252 else close.max()
    pct_from_high = (latest / high_52w) if high_52w > 0 else 0
    near_high = pct_from_high >= 0.95
    if near_high:
        score += 2
    details["52w_high"] = {
        "pct_from_high": round(pct_from_high * 100, 1),
        "near": near_high,
        "score": 2 if near_high else 0,
    }

    # 5. SMA trend: 20 SMA > 60 SMA (+2)
    sma20 = calc_sma(close, 20)
    sma60 = calc_sma(close, 60)
    if not sma20.empty and not sma60.empty:
        sma20_val = sma20.iloc[-1]
        sma60_val = sma60.iloc[-1]
        uptrend = sma20_val > sma60_val
        if uptrend:
            score += 2
        details["sma_trend"] = {"uptrend": uptrend, "score": 2 if uptrend else 0}

    return {"total": min(score, 20), "details": details}


def score_rsi_divergence(df: pd.DataFrame) -> dict:
    """
    RSI 다이버전스 점수 (v03 엔진 사용).

    Regular Bullish: +5
    Hidden Bullish: +3
    Regular Bearish: -3
    Hidden Bearish: -2
    """
    if compute_rsi_signals is None:
        return {"total": 0, "signals": []}

    try:
        result = compute_rsi_signals(df)
        signals = result.get("signals", []) if isinstance(result, dict) else []

        score = 0
        bonus_map = {
            "regular_bullish": 5,
            "hidden_bullish": 3,
            "regular_bearish": -3,
            "hidden_bearish": -2,
        }

        for sig in signals:
            sig_type = sig.signal_type if hasattr(sig, "signal_type") else sig.get("signal_type", "")
            score += bonus_map.get(sig_type, 0)

        return {"total": max(score, 0), "signal_count": len(signals)}

    except Exception as e:
        logger.warning(f"RSI divergence scoring failed: {e}")
        return {"total": 0, "signals": []}
