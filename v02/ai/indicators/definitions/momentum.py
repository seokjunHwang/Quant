"""Momentum indicators: RSI, MACD, Stochastic."""

import pandas as pd
import pandas_ta as ta


def _to_records(series: pd.Series, name: str = "value") -> list[dict]:
    """Convert pandas Series to [{time, value}] records."""
    df = series.dropna().reset_index()
    df.columns = ["time", name]
    df["time"] = df["time"].astype(str)
    return df.to_dict("records")


def compute_rsi(df: pd.DataFrame, length: int = 14) -> list[dict]:
    rsi = ta.rsi(df["close"], length=length)
    return _to_records(rsi)


def compute_macd(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> list[dict]:
    macd_df = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
    if macd_df is None:
        return []
    macd_df = macd_df.dropna()
    records = []
    for idx, row in macd_df.iterrows():
        records.append({
            "time": str(idx),
            "macd": round(row.iloc[0], 6),
            "signal": round(row.iloc[1], 6),
            "histogram": round(row.iloc[2], 6),
        })
    return records


def compute_stochastic(df: pd.DataFrame, k: int = 14, d: int = 3) -> list[dict]:
    stoch = ta.stoch(df["high"], df["low"], df["close"], k=k, d=d)
    if stoch is None:
        return []
    stoch = stoch.dropna()
    records = []
    for idx, row in stoch.iterrows():
        records.append({
            "time": str(idx),
            "k": round(row.iloc[0], 4),
            "d": round(row.iloc[1], 4),
        })
    return records
