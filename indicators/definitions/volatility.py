"""Volatility indicators: ATR."""

import pandas as pd
import pandas_ta as ta


def _to_records(series: pd.Series, name: str = "value") -> list[dict]:
    df = series.dropna().reset_index()
    df.columns = ["time", name]
    df["time"] = df["time"].astype(str)
    return df.to_dict("records")


def compute_atr(df: pd.DataFrame, length: int = 14) -> list[dict]:
    atr = ta.atr(df["high"], df["low"], df["close"], length=length)
    return _to_records(atr)
