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


def _standardize_ohlcv(df: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    """Standardize column names, timezone, and dedup timestamps."""
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

    # Remove duplicate timestamps (DST transitions can cause duplicates)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


# Fallback periods: try progressively shorter if the main period returns empty
_FALLBACK_PERIODS = [500, 300, 180]


def fetch_1h_candles(ticker: str, days: int | None = None) -> pd.DataFrame | None:
    """
    Fetch 1-hour candles from yfinance.
    yfinance supports 1h interval for up to 730 days.
    Falls back to shorter periods for recently listed stocks.
    """
    days = days or settings.FETCH_DAYS
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=f"{days}d", interval="1h", prepost=True)

        # Fallback: progressively try shorter periods
        if df.empty:
            for fallback in _FALLBACK_PERIODS:
                if fallback >= days:
                    continue
                try:
                    df = t.history(period=f"{fallback}d", interval="1h", prepost=True)
                except Exception as e:
                    logger.debug(f"[{ticker}] Fallback {fallback}d failed: {e}")
                    continue
                if not df.empty:
                    logger.info(f"[{ticker}] Fallback to {fallback}d: {len(df)} bars")
                    break

        if df.empty:
            logger.warning(f"[{ticker}] No 1h data returned after all fallbacks")
            return None

        return _standardize_ohlcv(df, ticker)

    except Exception as e:
        logger.error(f"[{ticker}] Failed to fetch 1h data: {e}")
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
    if df_1h is None or len(df_1h) < 8:
        return None

    df_4h = resample_to_4h(df_1h)

    if len(df_4h) < 5:
        logger.warning(f"[{ticker}] Too few 4h candles after resampling: {len(df_4h)}")
        return None

    return df_4h


def fetch_batch(
    tickers: list[str],
    interval: str = "4h",
    days: int | None = None,
    max_workers: int | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Fetch candles for multiple tickers in parallel.
    Uses ThreadPoolExecutor since yfinance is synchronous/IO-bound.
    """
    days = days or settings.FETCH_DAYS
    max_workers = max_workers or settings.MAX_WORKERS
    results: dict[str, pd.DataFrame] = {}

    def _fetch_one(ticker: str) -> tuple[str, pd.DataFrame | None]:
        return ticker, fetch_candles(ticker, interval=interval, days=days)

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


def resample_to_4h_session(df_1h: pd.DataFrame) -> pd.DataFrame:
    """
    Resample 1h candles to 4h using US trading session boundaries.
    AM session: 09:30-13:30 ET (4 x 1h candles)
    PM session: 13:30-16:00 ET (3 x 1h candles)
    Produces 2 candles per trading day, matching TradingView 4H.
    """
    hours = df_1h.index.hour + df_1h.index.minute / 60.0
    tmp = df_1h.copy()
    tmp["_date"] = tmp.index.date
    tmp["_sess"] = (hours >= 13.5).astype(int)

    result = tmp.groupby(["_date", "_sess"]).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).reset_index()

    result.index = pd.DatetimeIndex([
        pd.Timestamp(r["_date"].year, r["_date"].month, r["_date"].day,
                     9 if r["_sess"] == 0 else 13, 30)
        for _, r in result.iterrows()
    ])
    result = result[["open", "high", "low", "close", "volume"]]
    return result


def _has_eth_data(df_1h: pd.DataFrame) -> bool:
    """Check if 1h data contains electronic trading hours (outside 9-17)."""
    hours = df_1h.index.hour
    return bool((hours < 9).any() or (hours >= 17).any())


def resample_to_4h_eth(df_1h: pd.DataFrame) -> pd.DataFrame:
    """
    Resample 1h to 4h for futures with Electronic Trading Hours.
    CME session: 18:00 ET → 17:00 ET next day (halt 17:00-18:00).
    4H blocks: 18-22, 22-02, 02-06, 06-10, 10-14, 14-18.
    Produces ~6 candles per trading day.

    Uses +6h time shift so 18:00 session open aligns with midnight,
    then standard pandas 4h resample, then shift back.
    """
    tmp = df_1h[["open", "high", "low", "close", "volume"]].copy()
    tmp.index = tmp.index + pd.Timedelta(hours=6)

    result = tmp.resample("4h").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna(subset=["open", "close"])

    result.index = result.index - pd.Timedelta(hours=6)
    return result


def fetch_4h_candles_session(ticker: str, days: int = 730) -> pd.DataFrame | None:
    """
    Fetch session-based 4H candles (matches TradingView alignment).
    Auto-detects ETH (futures) vs RTH (stocks) and uses appropriate resampling.
    """
    df_1h = fetch_1h_candles(ticker, days)
    if df_1h is None or len(df_1h) < 8:
        return None

    if _has_eth_data(df_1h):
        df_4h = resample_to_4h_eth(df_1h)
        logger.info(f"[{ticker}] ETH detected → {len(df_4h)} 4h candles (~6/day)")
    else:
        df_4h = resample_to_4h_session(df_1h)
        logger.info(f"[{ticker}] RTH only → {len(df_4h)} 4h candles (2/day)")

    if len(df_4h) < 5:
        logger.warning(f"[{ticker}] Too few 4h candles: {len(df_4h)}")
        return None

    return df_4h


def fetch_daily_candles(ticker: str, days: int = 730) -> pd.DataFrame | None:
    """Fetch daily candles from yfinance with fallback for recently listed stocks."""
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=f"{days}d", interval="1d")

        # Fallback: progressively try shorter periods
        if df.empty:
            for fallback in _FALLBACK_PERIODS:
                if fallback >= days:
                    continue
                try:
                    df = t.history(period=f"{fallback}d", interval="1d")
                except Exception as e:
                    logger.debug(f"[{ticker}] Daily fallback {fallback}d failed: {e}")
                    continue
                if not df.empty:
                    logger.info(f"[{ticker}] Daily fallback to {fallback}d: {len(df)} bars")
                    break

        if df.empty:
            logger.warning(f"[{ticker}] No daily data returned after all fallbacks")
            return None

        return _standardize_ohlcv(df, ticker)
    except Exception as e:
        logger.error(f"[{ticker}] Failed to fetch daily data: {e}")
        return None


def fetch_15m_candles(ticker: str, days: int = 60) -> pd.DataFrame | None:
    """Fetch 15-minute candles from yfinance (max 60 days)."""
    days = min(days, 60)  # yfinance 15m limit
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=f"{days}d", interval="15m", prepost=True)

        if df.empty:
            for fallback in [30, 14]:
                if fallback >= days:
                    continue
                try:
                    df = t.history(period=f"{fallback}d", interval="15m", prepost=True)
                except Exception:
                    continue
                if not df.empty:
                    logger.info(f"[{ticker}] 15m fallback to {fallback}d: {len(df)} bars")
                    break

        if df.empty:
            logger.warning(f"[{ticker}] No 15m data returned")
            return None

        return _standardize_ohlcv(df, ticker)
    except Exception as e:
        logger.error(f"[{ticker}] Failed to fetch 15m data: {e}")
        return None


def resample_to_weekly(df_daily: pd.DataFrame) -> pd.DataFrame:
    """Resample daily candles to weekly candles."""
    df_w = df_daily.resample("W").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna(subset=["open", "close"])
    return df_w


def fetch_candles(ticker: str, interval: str = "4h", days: int = 730) -> pd.DataFrame | None:
    """
    Fetch candles at the given interval.
    Supported: '15m', '1h', '4h', '1d', '1w'
    """
    if interval == "15m":
        df = fetch_15m_candles(ticker, days)
    elif interval == "1h":
        df = fetch_1h_candles(ticker, days)
    elif interval == "1d":
        df = fetch_daily_candles(ticker, days)
    elif interval == "1w":
        df_d = fetch_daily_candles(ticker, days)
        df = resample_to_weekly(df_d) if df_d is not None else None
    else:  # 4h (default)
        df = fetch_4h_candles_session(ticker, days)

    if df is None or len(df) < 5:
        return None
    return df


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
