from __future__ import annotations
"""
Step 1-2: 시장 수치 데이터 수집.
yfinance(미장) + pykrx(국장) + 매크로 지표.
"""

import logging
from datetime import timedelta

from src.utils.config import now_kst

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# ── 매크로 지표 ──────────────────────────────────────────────

MACRO_TICKERS = {
    "vix":          "^VIX",
    "sp500":        "^GSPC",
    "nasdaq":       "^IXIC",
    "us10y_yield":  "^TNX",
    "us2y_yield":   "^IRX",
    "dollar_index": "DX-Y.NYB",
    "gold":         "GC=F",
    "oil_wti":      "CL=F",
    "bitcoin":      "BTC-USD",
}

KR_MACRO_TICKERS = {
    "kospi":  "^KS11",
    "kosdaq": "^KQ11",
    "usdkrw": "KRW=X",
}


def fetch_macro() -> dict:
    """글로벌 매크로 수치 수집."""
    result = {}
    all_tickers = {**MACRO_TICKERS, **KR_MACRO_TICKERS}

    for name, ticker in all_tickers.items():
        try:
            t = yf.Ticker(ticker)
            price = t.fast_info.last_price
            prev = t.fast_info.previous_close
            if price and prev:
                result[name] = {
                    "price": round(price, 4),
                    "prev_close": round(prev, 4),
                    "change_pct": round((price - prev) / prev * 100, 2),
                }
        except Exception as e:
            logger.warning(f"Macro [{name}] failed: {e}")

    # VIX 상태
    vix = result.get("vix", {}).get("price", 0)
    result["vix_zone"] = (
        "극공포" if vix >= 40 else
        "공포" if vix >= 30 else
        "긴장" if vix >= 20 else
        "평시"
    )

    return result


# ── 미장 종목 유니버스 ────────────────────────────────────────

def get_us_universe() -> pd.DataFrame:
    """S&P500 + NASDAQ100 종목 리스트 (섹터 포함)."""
    try:
        sp500 = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
        sp500 = sp500[["Symbol", "Security", "GICS Sector"]].rename(columns={
            "Symbol": "ticker", "Security": "name", "GICS Sector": "sector"
        })
        sp500["index"] = "SP500"
        logger.info(f"SP500: {len(sp500)} stocks")
        return sp500
    except Exception as e:
        logger.error(f"US universe fetch failed: {e}")
        return pd.DataFrame(columns=["ticker", "name", "sector", "index"])


# ── 국장 종목 유니버스 ────────────────────────────────────────

def get_kr_universe() -> pd.DataFrame:
    """KOSPI200 + KOSDAQ150 종목 리스트."""
    try:
        from pykrx import stock

        today = now_kst().strftime("%Y%m%d")

        rows = []
        for market in ["KOSPI", "KOSDAQ"]:
            tickers = stock.get_market_ticker_list(today, market=market)
            for ticker in tickers:
                name = stock.get_market_ticker_name(ticker)
                rows.append({"ticker": ticker, "name": name, "market": market})

        df = pd.DataFrame(rows)
        logger.info(f"KR universe: {len(df)} stocks")
        return df
    except ImportError:
        logger.error("pykrx not installed: pip install pykrx")
        return pd.DataFrame(columns=["ticker", "name", "market"])
    except Exception as e:
        logger.error(f"KR universe fetch failed: {e}")
        return pd.DataFrame(columns=["ticker", "name", "market"])


# ── 개별 종목 OHLCV ──────────────────────────────────────────

def fetch_ohlcv(ticker: str, days: int = 90, market: str = "us") -> pd.DataFrame | None:
    """종목 OHLCV 수집."""
    try:
        if market == "kr":
            from pykrx import stock
            end = now_kst().strftime("%Y%m%d")
            start = (now_kst() - timedelta(days=days)).strftime("%Y%m%d")
            df = stock.get_market_ohlcv_by_date(start, end, ticker)
            df.columns = ["open", "high", "low", "close", "volume", "trading_value", "price_change", "change_pct"]
            df.index = pd.to_datetime(df.index)
            return df[["open", "high", "low", "close", "volume"]]
        else:
            t = yf.Ticker(ticker)
            df = t.history(period=f"{days}d", interval="1d")
            if df.empty:
                return None
            return df[["Open", "High", "Low", "Close", "Volume"]].rename(columns=str.lower)
    except Exception as e:
        logger.warning(f"OHLCV [{ticker}] failed: {e}")
        return None


def fetch_stock_info(ticker: str, market: str = "us") -> dict:
    """종목 기본 정보 (시총, 현재가 등)."""
    try:
        if market == "us":
            t = yf.Ticker(ticker)
            info = t.fast_info
            return {
                "ticker": ticker,
                "market_cap": getattr(info, "market_cap", 0) or 0,
                "current_price": getattr(info, "last_price", 0) or 0,
                "avg_volume": getattr(info, "three_month_average_volume", 0) or 0,
            }
        else:
            from pykrx import stock
            today = now_kst().strftime("%Y%m%d")
            df = stock.get_market_cap_by_ticker(today, market="ALL")
            if ticker in df.index:
                row = df.loc[ticker]
                return {
                    "ticker": ticker,
                    "market_cap": int(row.get("시가총액", 0)),
                    "current_price": int(row.get("종가", 0)),
                    "avg_volume": int(row.get("거래량", 0)),
                }
    except Exception as e:
        logger.warning(f"Stock info [{ticker}] failed: {e}")
    return {"ticker": ticker, "market_cap": 0, "current_price": 0, "avg_volume": 0}
