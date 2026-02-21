"""
Data Fetcher: yfinance wrapper with 1h -> 4h resampling.
Handles both US and KR markets via yfinance.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf

from app.config import settings

logger = logging.getLogger(__name__)


def fetch_1h_candles(ticker: str, days: int | None = None) -> pd.DataFrame | None:
    """
    Fetch 1-hour candles from yfinance.
    yfinance supports 1h interval for up to 730 days.
    """
    days = days or settings.FETCH_DAYS
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=f"{days}d", interval="1h")

        if df.empty:
            logger.warning(f"[{ticker}] No data returned from yfinance")
            return None

        # Standardize columns
        df.columns = [c.lower() for c in df.columns]
        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(set(df.columns)):
            logger.warning(f"[{ticker}] Missing required columns: {required - set(df.columns)}")
            return None

        df = df[["open", "high", "low", "close", "volume"]].copy()
        df.index = pd.to_datetime(df.index)

        # Remove timezone info for consistency
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        return df

    except Exception as e:
        logger.error(f"[{ticker}] Failed to fetch data: {e}")
        return None


def resample_to_4h(df_1h: pd.DataFrame) -> pd.DataFrame:
    """
    Resample 1-hour candles to 4-hour candles.
    Uses standard OHLCV aggregation.
    """
    df_4h = df_1h.resample("4h").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna(subset=["open", "close"])

    return df_4h


def fetch_4h_candles(ticker: str, days: int | None = None) -> pd.DataFrame | None:
    """
    Fetch 4-hour candles: get 1h data then resample to 4h.
    Returns DataFrame with ~90-120 candles for 20 days.
    """
    df_1h = fetch_1h_candles(ticker, days)
    if df_1h is None or len(df_1h) < 20:
        return None

    df_4h = resample_to_4h(df_1h)

    if len(df_4h) < 30:
        logger.warning(f"[{ticker}] Too few 4h candles after resampling: {len(df_4h)}")
        return None

    return df_4h


def fetch_batch(
    tickers: list[str],
    days: int | None = None,
    max_workers: int | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Fetch 4h candles for multiple tickers in parallel.
    Uses ThreadPoolExecutor since yfinance is synchronous/IO-bound.
    """
    days = days or settings.FETCH_DAYS
    max_workers = max_workers or settings.MAX_WORKERS
    results: dict[str, pd.DataFrame] = {}

    def _fetch_one(ticker: str) -> tuple[str, pd.DataFrame | None]:
        return ticker, fetch_4h_candles(ticker, days)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, t): t for t in tickers}

        for future in as_completed(futures):
            ticker = futures[future]
            try:
                t, df = future.result()
                if df is not None:
                    results[t] = df
                else:
                    logger.warning(f"[{ticker}] Skipped (no data)")
            except Exception as e:
                logger.error(f"[{ticker}] Exception during fetch: {e}")

    logger.info(f"Fetched {len(results)}/{len(tickers)} tickers successfully")
    return results


def get_current_price(ticker: str) -> float | None:
    """Get the latest price for a ticker."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1d", interval="1m")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        # Fallback to daily
        hist = t.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None
