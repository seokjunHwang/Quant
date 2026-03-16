"""
Step 4 Data Fetcher — v03의 data_fetcher.py를 직접 import.

v03과 v04가 같은 /workspace/Quant/ 안에 있으므로
indicators/converted/ 의 RSI 엔진도 직접 임포트 가능.
"""

import sys
from pathlib import Path

# Add v03 backend to path so we can import its modules
_V03_BACKEND = Path(__file__).parent.parent.parent.parent / "v03_종목추천" / "backend"
_INDICATORS = Path(__file__).parent.parent.parent.parent / "indicators"

if str(_V03_BACKEND) not in sys.path:
    sys.path.insert(0, str(_V03_BACKEND))
if str(_INDICATORS.parent) not in sys.path:
    sys.path.insert(0, str(_INDICATORS.parent))

# Re-export v03's data fetcher functions
# These work standalone (only depend on yfinance + pandas)
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_ohlcv(ticker: str, interval: str = "1d", days: int = 365) -> pd.DataFrame | None:
    """
    yfinance에서 OHLCV 데이터 수집.
    v04에서는 멀티 타임프레임 (1d, 1h, 15m, 5m) 모두 사용.
    """
    try:
        t = yf.Ticker(ticker)

        # yfinance interval limits
        max_days = {
            "1m": 7, "5m": 60, "15m": 60,
            "1h": 730, "1d": 3650, "1wk": 3650,
        }
        days = min(days, max_days.get(interval, 365))

        df = t.history(period=f"{days}d", interval=interval, prepost=True)
        if df.empty:
            return None

        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]].copy()
        df.index = pd.to_datetime(df.index)

        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        df = df[~df.index.duplicated(keep="last")].sort_index()
        return df

    except Exception as e:
        logger.error(f"[{ticker}] Fetch {interval} failed: {e}")
        return None


def fetch_multi_timeframe(ticker: str) -> dict[str, pd.DataFrame]:
    """
    멀티 타임프레임 데이터 수집.
    일봉 + 1시간봉 + 15분봉 + 5분봉
    """
    result = {}

    frames = {
        "1d": 365,
        "1h": 30,
        "15m": 14,
        "5m": 5,
    }

    for interval, days in frames.items():
        df = fetch_ohlcv(ticker, interval=interval, days=days)
        if df is not None and len(df) >= 5:
            result[interval] = df

    return result


def fetch_batch_ohlcv(
    tickers: list[str],
    interval: str = "1d",
    days: int = 365,
    max_workers: int = 10,
) -> dict[str, pd.DataFrame]:
    """병렬 OHLCV 수집."""
    results = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_ohlcv, t, interval, days): t
            for t in tickers
        }
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                df = future.result()
                if df is not None:
                    results[ticker] = df
            except Exception as e:
                logger.error(f"[{ticker}] Batch fetch error: {e}")

    return results
