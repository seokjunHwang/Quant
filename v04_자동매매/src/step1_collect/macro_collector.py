"""
Step 1-2: 매크로 선행 데이터 수집.

FRED API (무료): 국채 수익률, 달러인덱스, VIX
Yahoo Finance (무료): 금/유가 선물, VIX 실시간
"""

import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from src.utils.config import FRED_API_KEY

logger = logging.getLogger(__name__)

# FRED series IDs
FRED_SERIES = {
    "us10y": "DGS10",          # 10yr Treasury yield
    "us2y": "DGS2",            # 2yr Treasury yield
    "fed_funds": "FEDFUNDS",   # Fed Funds Rate
    "dollar_index": "DTWEXBGS",  # Trade-Weighted Dollar Index
    "breakeven_5y": "T5YIE",   # 5yr Breakeven Inflation Rate
}

# Yahoo Finance tickers for real-time
YF_TICKERS = {
    "vix": "^VIX",
    "gold": "GC=F",
    "oil_wti": "CL=F",
    "oil_brent": "BZ=F",
    "natural_gas": "NG=F",
    "copper": "HG=F",
    "dollar_index": "DX-Y.NYB",
    "us10y_yield": "^TNX",
    "us2y_yield": "^IRX",  # 13-week T-bill (proxy)
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
}


def fetch_fred_data(days: int = 30) -> dict[str, pd.Series]:
    """FRED API에서 매크로 데이터 수집."""
    if not FRED_API_KEY:
        logger.warning("FRED_API_KEY not set, skipping FRED data")
        return {}

    try:
        from fredapi import Fred
        fred = Fred(api_key=FRED_API_KEY)
    except Exception as e:
        logger.error(f"FRED init failed: {e}")
        return {}

    end = datetime.now()
    start = end - timedelta(days=days)
    data = {}

    for name, series_id in FRED_SERIES.items():
        try:
            series = fred.get_series(series_id, start, end)
            if series is not None and not series.empty:
                data[name] = series.dropna()
                logger.debug(f"FRED [{name}]: {len(series)} points")
        except Exception as e:
            logger.warning(f"FRED [{name}] failed: {e}")

    return data


def fetch_realtime_macro() -> dict[str, dict]:
    """
    Yahoo Finance에서 실시간 매크로 데이터 수집.

    Returns:
        {ticker_name: {price, change_pct, prev_close, ...}}
    """
    data = {}

    for name, ticker in YF_TICKERS.items():
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            price = getattr(info, "last_price", None)
            prev = getattr(info, "previous_close", None)

            if price is None:
                continue

            change_pct = ((price - prev) / prev * 100) if prev else 0.0

            data[name] = {
                "ticker": ticker,
                "price": round(price, 4),
                "prev_close": round(prev, 4) if prev else None,
                "change_pct": round(change_pct, 2),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(f"YF [{name}] failed: {e}")

    return data


def get_vix() -> dict:
    """VIX 현재값 + 가산점 계산."""
    try:
        t = yf.Ticker("^VIX")
        price = t.fast_info.last_price
        prev = t.fast_info.previous_close
        change_pct = ((price - prev) / prev * 100) if prev else 0.0

        # VIX 가산점 계산
        if price >= 50:
            bonus = 10
            zone = "극공포"
        elif price >= 30:
            bonus = 7
            zone = "공포"
        elif price >= 20:
            bonus = 3
            zone = "긴장"
        else:
            bonus = 0
            zone = "평시"

        return {
            "vix": round(price, 2),
            "prev_close": round(prev, 2) if prev else None,
            "change_pct": round(change_pct, 2),
            "zone": zone,
            "bonus": bonus,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"VIX fetch failed: {e}")
        return {"vix": 0, "zone": "unknown", "bonus": 0}


def detect_macro_anomalies(macro_data: dict[str, dict]) -> list[dict]:
    """
    매크로 데이터에서 이상 신호를 감지.

    이상 신호 기준:
    - VIX 일간 변동 10%+
    - 국채 수익률 급변 (5%+)
    - 달러인덱스 급변 (1%+)
    - 금/유가 급변 (3%+)
    """
    anomalies = []

    thresholds = {
        "vix": 10.0,
        "us10y_yield": 5.0,
        "us2y_yield": 5.0,
        "dollar_index": 1.0,
        "gold": 3.0,
        "oil_wti": 5.0,
        "oil_brent": 5.0,
        "natural_gas": 7.0,
        "copper": 4.0,
    }

    for name, threshold in thresholds.items():
        info = macro_data.get(name)
        if not info:
            continue

        change = abs(info.get("change_pct", 0))
        if change >= threshold:
            direction = "급등" if info["change_pct"] > 0 else "급락"
            anomalies.append({
                "signal_type": "macro_anomaly",
                "source": name,
                "description": f"{name} {direction} ({info['change_pct']:+.1f}%)",
                "value": info["price"],
                "change_pct": info["change_pct"],
                "severity": "high" if change >= threshold * 1.5 else "medium",
                "timestamp": info.get("timestamp", datetime.now().isoformat()),
            })

    # Yield curve inversion check
    us10y = macro_data.get("us10y_yield", {}).get("price")
    us2y = macro_data.get("us2y_yield", {}).get("price")
    if us10y and us2y and us2y > us10y:
        anomalies.append({
            "signal_type": "macro_anomaly",
            "source": "yield_curve",
            "description": f"수익률 역전 (2Y={us2y:.2f}% > 10Y={us10y:.2f}%)",
            "value": us2y - us10y,
            "change_pct": 0,
            "severity": "high",
            "timestamp": datetime.now().isoformat(),
        })

    return anomalies


def collect_all_macro() -> dict:
    """매크로 데이터 전체 수집 + 이상 신호 감지."""
    macro = fetch_realtime_macro()
    vix = get_vix()
    anomalies = detect_macro_anomalies(macro)

    return {
        "macro_data": macro,
        "vix": vix,
        "anomalies": anomalies,
        "collected_at": datetime.now().isoformat(),
    }
