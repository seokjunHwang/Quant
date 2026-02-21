"""
Stock Filtering Module.
Applies market cap, liquidity, volatility, risk, and trend filters.
Used primarily for stock pool construction/rebalancing.
"""

import logging

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def filter_by_market_cap(info: dict, market: str) -> bool:
    """
    US: $2B ~ $50B
    KR: 5,000억원 ~ 10조원 (approx $375M ~ $7.5B at 1330 KRW/USD)
    """
    cap = info.get("marketCap")
    if cap is None:
        return False

    if market == "US":
        return 2_000_000_000 <= cap <= 50_000_000_000
    elif market == "KR":
        return 500_000_000_000 <= cap <= 10_000_000_000_000
    return False


def filter_by_liquidity(info: dict, market: str) -> bool:
    """
    Average daily trading value (20-day).
    US: $10M+
    KR: 50억원+ (approx $3.75M)
    """
    avg_vol = info.get("averageVolume")
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if avg_vol is None or price is None:
        return False

    avg_value = avg_vol * price

    if market == "US":
        return avg_value >= 10_000_000
    elif market == "KR":
        return avg_value >= 5_000_000_000
    return False


def filter_by_volatility(info: dict) -> bool:
    """
    Beta: 0.8 ~ 1.8
    """
    beta = info.get("beta")
    if beta is None:
        return True  # Pass if beta not available
    return 0.8 <= beta <= 1.8


def filter_by_risk(info: dict, market: str) -> bool:
    """
    D/E ratio < 200%
    Short interest < 15% (US only)
    """
    de = info.get("debtToEquity")
    if de is not None and de > 200:
        return False

    if market == "US":
        short_pct = info.get("shortPercentOfFloat")
        if short_pct is not None and short_pct > 0.15:
            return False

    return True


def filter_by_trend(df: pd.DataFrame) -> bool:
    """
    20 SMA > 60 SMA (medium-term uptrend)
    """
    if len(df) < 60:
        return True  # Pass if not enough data

    close = df["close"] if "close" in df.columns else df["Close"]
    sma_20 = close.rolling(20).mean().iloc[-1]
    sma_60 = close.rolling(60).mean().iloc[-1]

    if np.isnan(sma_20) or np.isnan(sma_60):
        return True

    return sma_20 > sma_60


def apply_all_filters(ticker: str, market: str) -> bool:
    """Apply all filters to a single ticker."""
    try:
        t = yf.Ticker(ticker)
        info = t.info

        if not filter_by_market_cap(info, market):
            logger.debug(f"[{ticker}] Failed market cap filter")
            return False
        if not filter_by_liquidity(info, market):
            logger.debug(f"[{ticker}] Failed liquidity filter")
            return False
        if not filter_by_volatility(info):
            logger.debug(f"[{ticker}] Failed volatility filter")
            return False
        if not filter_by_risk(info, market):
            logger.debug(f"[{ticker}] Failed risk filter")
            return False

        # Trend filter needs price data
        hist = t.history(period="6mo")
        if not hist.empty:
            hist.columns = [c.lower() for c in hist.columns]
            if not filter_by_trend(hist):
                logger.debug(f"[{ticker}] Failed trend filter")
                return False

        return True

    except Exception as e:
        logger.error(f"[{ticker}] Filter error: {e}")
        return False
