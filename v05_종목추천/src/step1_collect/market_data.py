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


def _last_trading_date() -> str:
    """가장 최근 거래일 (주말이면 금요일로)."""
    dt = now_kst()
    while dt.weekday() >= 5:  # 5=토, 6=일
        dt -= timedelta(days=1)
    return dt.strftime("%Y%m%d")


# ── KR 시총 캐시 (종목마다 KRX 호출 방지) ──────────────────────
_kr_cap_cache: pd.DataFrame | None = None
_kr_cap_date: str = ""
_kr_cap_tried: str = ""  # 이 거래일에 대해 벌크 조회를 이미 시도했는지


def _get_kr_market_cap() -> pd.DataFrame:
    """
    KR 전체 시총 DataFrame — 1회 호출 후 캐시.
    데이터 없으면 최대 5일 전까지 시도하고, 실패해도 같은 세션에서 재시도하지 않음
    (종목 수만큼 retry 폭주 방지).
    """
    global _kr_cap_cache, _kr_cap_date, _kr_cap_tried
    trade_date = _last_trading_date()
    if _kr_cap_tried == trade_date:
        return _kr_cap_cache if _kr_cap_cache is not None else pd.DataFrame()

    from pykrx import stock
    dt = now_kst()
    for _ in range(5):
        while dt.weekday() >= 5:
            dt -= timedelta(days=1)
        try_date = dt.strftime("%Y%m%d")
        try:
            df = stock.get_market_cap_by_ticker(try_date, market="ALL")
            if not df.empty and "시가총액" in df.columns:
                _kr_cap_cache = df
                _kr_cap_date = trade_date
                _kr_cap_tried = trade_date
                logger.info(f"KR market cap loaded ({try_date}, {len(df)} stocks)")
                return df
        except Exception:
            pass
        dt -= timedelta(days=1)

    # 벌크 실패: 네거티브 캐시 기록 → fetch_stock_info가 yfinance fallback으로 전환
    _kr_cap_tried = trade_date
    _kr_cap_cache = None
    logger.warning("KR market cap 벌크 조회 실패 — 종목별 yfinance fallback 사용")
    return pd.DataFrame()


# ── KR 시총 fallback: yfinance (.KS / .KQ) ─────────────────────
_kr_yf_cache: dict[str, dict] = {}


def _fetch_kr_info_yf(ticker: str) -> dict:
    """
    pykrx 벌크 실패 시 단일 종목 시총/가격을 yfinance로 조회.
    KOSPI는 .KS, KOSDAQ은 .KQ suffix. 어느 쪽인지 모르면 둘 다 시도.
    """
    if ticker in _kr_yf_cache:
        return _kr_yf_cache[ticker]

    result: dict = {}
    for suffix in (".KS", ".KQ"):
        try:
            t = yf.Ticker(f"{ticker}{suffix}")
            fi = t.fast_info
            mc = getattr(fi, "market_cap", 0) or 0
            price = getattr(fi, "last_price", 0) or 0
            vol = getattr(fi, "three_month_average_volume", 0) or 0
            if mc > 0 or price > 0:
                result = {
                    "market_cap": int(mc),
                    "current_price": int(price),
                    "avg_volume": int(vol),
                }
                break
        except Exception:
            continue

    _kr_yf_cache[ticker] = result
    return result


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

        today = _last_trading_date()

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
            end = _last_trading_date()
            start = (now_kst() - timedelta(days=days)).strftime("%Y%m%d")
            df = stock.get_market_ohlcv_by_date(start, end, ticker)
            if df.empty:
                return None
            # pykrx 칼럼 수가 버전마다 다름 — 이름 기반으로 매핑
            col_map = {}
            for col in df.columns:
                cl = str(col).lower()
                if "시가" in cl:
                    col_map[col] = "open"
                elif "고가" in cl:
                    col_map[col] = "high"
                elif "저가" in cl:
                    col_map[col] = "low"
                elif "종가" in cl:
                    col_map[col] = "close"
                elif "거래량" in cl:
                    col_map[col] = "volume"
            df = df.rename(columns=col_map)
            df.index = pd.to_datetime(df.index)
            need = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
            return df[need] if need else None
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
            df = _get_kr_market_cap()
            if not df.empty and ticker in df.index:
                row = df.loc[ticker]
                return {
                    "ticker": ticker,
                    "market_cap": int(row.get("시가총액", 0)),
                    "current_price": int(row.get("종가", 0)),
                    "avg_volume": int(row.get("거래량", 0)),
                }
            # pykrx 벌크 실패 or 티커 미존재 → yfinance fallback
            fb = _fetch_kr_info_yf(ticker)
            if fb:
                return {"ticker": ticker, **fb}
    except Exception as e:
        logger.warning(f"Stock info [{ticker}] failed: {e}")
    return {"ticker": ticker, "market_cap": 0, "current_price": 0, "avg_volume": 0}
