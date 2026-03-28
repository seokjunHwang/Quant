from __future__ import annotations
"""
Step 4-1: 기술적 지표 계산.
RSI, 볼린저밴드, MACD, 거래량 이동평균.
"""

import logging

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def calc_bollinger(close: pd.Series, period: int = 20, std: float = 2.0) -> pd.DataFrame:
    mid = close.rolling(period).mean()
    sigma = close.rolling(period).std()
    return pd.DataFrame({
        "bb_upper": mid + std * sigma,
        "bb_mid": mid,
        "bb_lower": mid - std * sigma,
        "bb_pct": (close - (mid - std * sigma)) / (2 * std * sigma),
    })


def calc_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({
        "macd": macd_line,
        "macd_signal": signal_line,
        "macd_hist": histogram,
    })


def calc_volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """현재 거래량 / 20일 평균거래량."""
    avg = volume.rolling(period).mean()
    return volume / avg.replace(0, np.nan)


def analyze_chart(df: pd.DataFrame) -> dict:
    """
    OHLCV DataFrame → 기술적 지표 요약.

    Returns:
        {
            "rsi": float,
            "rsi_signal": "과매수/과매도/중립",
            "bb_pct": float,  # 0=하단, 1=상단
            "macd_cross": "golden/dead/none",
            "volume_ratio": float,
            "trend": "uptrend/downtrend/sideways",
            "price_change_5d": float,  # 5일 등락률 %
            "price_change_20d": float,
            "support": float,
            "resistance": float,
        }
    """
    if df is None or len(df) < 26:
        return {}

    close = df["close"]
    volume = df["volume"] if "volume" in df.columns else pd.Series(dtype=float)

    # RSI
    rsi_series = calc_rsi(close)
    rsi = round(float(rsi_series.iloc[-1]), 1) if not rsi_series.empty else 50.0
    rsi_signal = "과매수" if rsi >= 70 else "과매도" if rsi <= 30 else "중립"

    # 볼린저
    bb = calc_bollinger(close)
    bb_pct = round(float(bb["bb_pct"].iloc[-1]), 3) if not bb.empty else 0.5

    # MACD
    macd_df = calc_macd(close)
    macd_cross = "none"
    if len(macd_df) >= 2:
        prev_hist = macd_df["macd_hist"].iloc[-2]
        curr_hist = macd_df["macd_hist"].iloc[-1]
        if prev_hist < 0 and curr_hist >= 0:
            macd_cross = "golden"
        elif prev_hist >= 0 and curr_hist < 0:
            macd_cross = "dead"

    # 거래량
    vol_ratio = 1.0
    if not volume.empty and len(volume) >= 20:
        vr = calc_volume_ratio(volume)
        vol_ratio = round(float(vr.iloc[-1]), 2)

    # 추세
    ma20 = close.rolling(20).mean().iloc[-1]
    ma60 = close.rolling(60).mean().iloc[-1] if len(close) >= 60 else ma20
    price_now = close.iloc[-1]
    if price_now > ma20 > ma60:
        trend = "uptrend"
    elif price_now < ma20 < ma60:
        trend = "downtrend"
    else:
        trend = "sideways"

    # 등락률
    price_change_5d = round((close.iloc[-1] / close.iloc[-6] - 1) * 100, 2) if len(close) >= 6 else 0.0
    price_change_20d = round((close.iloc[-1] / close.iloc[-21] - 1) * 100, 2) if len(close) >= 21 else 0.0

    # 지지/저항 (20일 저/고)
    support = round(float(close.rolling(20).min().iloc[-1]), 4)
    resistance = round(float(close.rolling(20).max().iloc[-1]), 4)

    return {
        "rsi": rsi,
        "rsi_signal": rsi_signal,
        "bb_pct": bb_pct,
        "macd_cross": macd_cross,
        "volume_ratio": vol_ratio,
        "trend": trend,
        "price_change_5d": price_change_5d,
        "price_change_20d": price_change_20d,
        "support": support,
        "resistance": resistance,
        "current_price": round(float(close.iloc[-1]), 4),
    }
