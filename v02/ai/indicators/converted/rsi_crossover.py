"""
Auto-converted from Pine Script: rsi_crossover.pine
Converted at: 2026-02-18T20:46:00
Model: claude-sonnet-4-20250514
source_hash: manual_test
Verification status: pending
"""
import pandas as pd
import numpy as np

# Use pandas-ta if available, otherwise compute RSI manually
try:
    import pandas_ta as ta
    HAS_TA = True
except ImportError:
    HAS_TA = False

METADATA = {
    "name": "RSI Crossover Strategy",
    "category": "momentum",
    "default_params": {"rsi_length": 14, "overbought": 70, "oversold": 30},
    "description": "RSI가 과매도 구간을 상향 돌파하면 매수, 과매수 구간을 하향 돌파하면 매도"
}


def _compute_rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """Compute RSI without pandas-ta."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=length, min_periods=length).mean()
    avg_loss = loss.rolling(window=length, min_periods=length).mean()
    # Use Wilder's smoothing after initial SMA
    for i in range(length, len(avg_gain)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (length - 1) + gain.iloc[i]) / length
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (length - 1) + loss.iloc[i]) / length
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def generate_signals(df: pd.DataFrame, rsi_length=14, overbought=70, oversold=30) -> pd.DataFrame:
    """RSI crossover signals: buy when RSI crosses above oversold, sell when crosses below overbought."""
    result = df.copy()

    # Calculate RSI
    if HAS_TA:
        result['rsi'] = ta.rsi(result['close'], length=rsi_length)
    else:
        result['rsi'] = _compute_rsi(result['close'], length=rsi_length)

    # Initialize signal
    result['signal'] = 0

    # Crossover: RSI crosses above oversold level (buy)
    rsi = result['rsi']
    buy_cross = (rsi > oversold) & (rsi.shift(1) <= oversold)
    result.loc[buy_cross, 'signal'] = 1

    # Crossunder: RSI crosses below overbought level (sell)
    sell_cross = (rsi < overbought) & (rsi.shift(1) >= overbought)
    result.loc[sell_cross, 'signal'] = -1

    return result
