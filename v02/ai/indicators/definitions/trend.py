"""Trend indicators: EMA, SMA, Bollinger Bands, ADX."""

import pandas as pd
import pandas_ta as ta


def _to_records(series: pd.Series, name: str = "value") -> list[dict]:
    df = series.dropna().reset_index()
    df.columns = ["time", name]
    df["time"] = df["time"].astype(str)
    return df.to_dict("records")


def compute_ema(df: pd.DataFrame, length: int = 20) -> list[dict]:
    ema = ta.ema(df["close"], length=length)
    return _to_records(ema)


def compute_sma(df: pd.DataFrame, length: int = 200) -> list[dict]:
    sma = ta.sma(df["close"], length=length)
    return _to_records(sma)


def compute_bollinger_bands(
    df: pd.DataFrame, length: int = 20, std: float = 2.0
) -> list[dict]:
    bb = ta.bbands(df["close"], length=length, std=std)
    if bb is None:
        return []
    bb = bb.dropna()
    records = []
    for idx, row in bb.iterrows():
        records.append({
            "time": str(idx),
            "lower": round(row.iloc[0], 6),
            "middle": round(row.iloc[1], 6),
            "upper": round(row.iloc[2], 6),
        })
    return records


def compute_adx(df: pd.DataFrame, length: int = 14) -> list[dict]:
    adx = ta.adx(df["high"], df["low"], df["close"], length=length)
    if adx is None:
        return []
    adx_col = adx.iloc[:, 0].dropna()
    return _to_records(adx_col)
