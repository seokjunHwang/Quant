"""데이터 수집: yfinance 1h → 장중 세션 기반 4h 캔들."""

import pandas as pd
import yfinance as yf


def fetch_4h(ticker: str, days: int = 730) -> pd.DataFrame:
    """
    yfinance에서 1h 데이터를 가져와 장중 4h 캔들로 변환.

    미국 장중(ET) 기준:
      전반 09:30-13:30 (1h봉 4개)
      후반 13:30-16:00 (1h봉 3개)
    → 하루 2개 4h 캔들. 트레이딩뷰 4h봉과 동일.

    Returns:
        OHLCV DataFrame (DatetimeIndex, 컬럼: open/high/low/close/volume)
    """
    df_1h = yf.Ticker(ticker).history(period=f"{days}d", interval="1h")
    if df_1h.empty:
        raise ValueError(f"[{ticker}] yfinance에서 데이터를 가져올 수 없음")

    df_1h.columns = [c.lower() for c in df_1h.columns]
    df_1h = df_1h[["open", "high", "low", "close", "volume"]].copy()

    hours = df_1h.index.hour + df_1h.index.minute / 60.0
    df_1h["_date"] = df_1h.index.date
    df_1h["_sess"] = (hours >= 13.5).astype(int)

    df = df_1h.groupby(["_date", "_sess"]).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).reset_index()

    df.index = pd.DatetimeIndex([
        pd.Timestamp(r["_date"].year, r["_date"].month, r["_date"].day,
                     9 if r["_sess"] == 0 else 13, 30)
        for _, r in df.iterrows()
    ])
    df = df[["open", "high", "low", "close", "volume"]]
    return df
