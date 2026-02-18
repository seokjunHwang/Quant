"""Volume indicators: OBV, Volume MA."""

import pandas as pd
import pandas_ta as ta


def _to_records(series: pd.Series, name: str = "value") -> list[dict]:
    df = series.dropna().reset_index()
    df.columns = ["time", name]
    df["time"] = df["time"].astype(str)
    return df.to_dict("records")


def compute_obv(df: pd.DataFrame) -> list[dict]:
    obv = ta.obv(df["close"], df["volume"])
    return _to_records(obv)


def compute_volume_ma(df: pd.DataFrame, length: int = 20) -> list[dict]:
    vol_ma = ta.sma(df["volume"], length=length)
    return _to_records(vol_ma)
