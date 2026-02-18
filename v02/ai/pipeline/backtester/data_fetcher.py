"""OHLCV data fetcher with local caching.

Supports crypto (ccxt/Binance) and stocks (yfinance).
"""

import hashlib
import pandas as pd
from pathlib import Path

from ai.pipeline.utils.logger import get_logger

logger = get_logger("data_fetcher")

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "price_cache"


def _cache_key(asset: str, timeframe: str, start: str, end: str) -> str:
    raw = f"{asset}_{timeframe}_{start}_{end}"
    return hashlib.md5(raw.encode()).hexdigest()


def _load_cache(cache_path: Path) -> pd.DataFrame | None:
    if cache_path.exists():
        df = pd.read_parquet(cache_path)
        logger.info(f"Cache hit: {cache_path.name} ({len(df)} rows)")
        return df
    return None


def _save_cache(df: pd.DataFrame, cache_path: Path):
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_path)
    logger.info(f"Cached: {cache_path.name} ({len(df)} rows)")


def _is_crypto(asset: str) -> bool:
    return "/" in asset or asset.upper().endswith("USDT")


def fetch_crypto(asset: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
    """Fetch crypto OHLCV via ccxt (Binance)."""
    import ccxt
    from datetime import datetime

    exchange = ccxt.binance({"enableRateLimit": True})

    # Normalize asset format: BTC/USDT
    symbol = asset if "/" in asset else f"{asset[:-4]}/{asset[-4:]}"

    tf_map = {"1d": "1d", "4h": "4h", "1h": "1h", "15m": "15m", "5m": "5m"}
    ccxt_tf = tf_map.get(timeframe, "1d")

    since = exchange.parse8601(f"{start}T00:00:00Z")
    end_ts = exchange.parse8601(f"{end}T23:59:59Z")

    all_candles = []
    while since < end_ts:
        candles = exchange.fetch_ohlcv(symbol, ccxt_tf, since=since, limit=1000)
        if not candles:
            break
        all_candles.extend(candles)
        since = candles[-1][0] + 1  # next ms after last candle

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("timestamp")
    df = df[df.index <= end]
    df.index.name = "date"

    logger.info(f"Fetched {symbol} {ccxt_tf}: {len(df)} candles ({start} ~ {end})")
    return df


def fetch_stock(asset: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
    """Fetch stock/ETF OHLCV via yfinance."""
    import yfinance as yf

    tf_map = {"1d": "1d", "1h": "1h", "5m": "5m"}
    yf_interval = tf_map.get(timeframe, "1d")

    ticker = yf.Ticker(asset)
    df = ticker.history(start=start, end=end, interval=yf_interval)
    df.columns = [c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]]
    df.index.name = "date"

    logger.info(f"Fetched {asset} {yf_interval}: {len(df)} candles ({start} ~ {end})")
    return df


def fetch_ohlcv(
    asset: str,
    timeframe: str = "1d",
    start: str = "2023-01-01",
    end: str = "2024-12-31",
    use_cache: bool = True,
) -> pd.DataFrame:
    """Fetch OHLCV data with caching. Auto-detects crypto vs stock.

    Args:
        asset: "BTC/USDT", "BTCUSDT", "SPY", "AAPL" etc.
        timeframe: "1d", "4h", "1h", "15m", "5m"
        start: Start date "YYYY-MM-DD"
        end: End date "YYYY-MM-DD"
        use_cache: Whether to use local parquet cache

    Returns:
        DataFrame with columns [open, high, low, close, volume] and DatetimeIndex.
    """
    # Check cache
    if use_cache:
        key = _cache_key(asset, timeframe, start, end)
        cache_path = CACHE_DIR / f"{key}.parquet"
        cached = _load_cache(cache_path)
        if cached is not None:
            return cached

    # Fetch from source
    if _is_crypto(asset):
        df = fetch_crypto(asset, timeframe, start, end)
    else:
        df = fetch_stock(asset, timeframe, start, end)

    # Save cache
    if use_cache and len(df) > 0:
        _save_cache(df, cache_path)

    return df
