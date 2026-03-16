"""
Step 1-1: 스마트머니 흔적 수집.

무료 소스:
- SEC EDGAR RSS: 내부자 매수/매도 (Form 4)
- Finnhub: 내부자 거래, 공매도, 기본 데이터
- yfinance: 기관 보유, 공매도 비율

유료 (향후 확장):
- Unusual Whales: 옵션 이상거래, 다크풀
"""

import logging
from datetime import datetime, timedelta

import yfinance as yf

from src.utils.config import FINNHUB_API_KEY

logger = logging.getLogger(__name__)


def fetch_insider_trades(ticker: str) -> list[dict]:
    """
    Finnhub에서 내부자 거래 데이터 수집.
    무료 tier: 60 call/min.
    """
    if not FINNHUB_API_KEY:
        return []

    try:
        import finnhub
        client = finnhub.Client(api_key=FINNHUB_API_KEY)

        today = datetime.now()
        from_date = (today - timedelta(days=90)).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")

        data = client.stock_insider_transactions(ticker, from_date, to_date)

        if not data or "data" not in data:
            return []

        trades = []
        for t in data["data"]:
            # Focus on large buys by C-level
            if t.get("transactionType") in ("P - Purchase", "A - Grant"):
                trades.append({
                    "signal_type": "insider_trade",
                    "ticker": ticker,
                    "person": t.get("name", "Unknown"),
                    "transaction": t.get("transactionType", ""),
                    "shares": t.get("share", 0),
                    "value": t.get("share", 0) * t.get("transactionPrice", 0),
                    "date": t.get("filingDate", ""),
                    "source": "finnhub",
                })

        return trades

    except Exception as e:
        logger.warning(f"Insider trades [{ticker}] failed: {e}")
        return []


def fetch_short_interest(ticker: str) -> dict | None:
    """yfinance에서 공매도 비율 수집."""
    try:
        t = yf.Ticker(ticker)
        info = t.info

        short_pct = info.get("shortPercentOfFloat")
        short_ratio = info.get("shortRatio")

        if short_pct is None:
            return None

        return {
            "ticker": ticker,
            "short_pct_float": round(float(short_pct) * 100, 2),
            "short_ratio": float(short_ratio) if short_ratio else None,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.warning(f"Short interest [{ticker}] failed: {e}")
        return None


def fetch_institutional_holders(ticker: str) -> dict | None:
    """yfinance에서 기관 보유 비율 수집."""
    try:
        t = yf.Ticker(ticker)
        info = t.info

        inst_pct = info.get("heldPercentInstitutions")
        if inst_pct is None:
            return None

        return {
            "ticker": ticker,
            "institutional_pct": round(float(inst_pct) * 100, 2),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.warning(f"Institutional [{ticker}] failed: {e}")
        return None


def detect_volume_surge(ticker: str, threshold: float = 2.0) -> dict | None:
    """
    거래량 급증 감지.
    최근 거래량 / 20일 평균 > threshold → 이상 신호.
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1mo")

        if hist is None or len(hist) < 5:
            return None

        avg_volume = hist["Volume"].iloc[:-1].mean()
        latest_volume = hist["Volume"].iloc[-1]

        if avg_volume == 0:
            return None

        ratio = latest_volume / avg_volume

        if ratio >= threshold:
            return {
                "signal_type": "volume_surge",
                "ticker": ticker,
                "latest_volume": int(latest_volume),
                "avg_volume": int(avg_volume),
                "surge_ratio": round(ratio, 2),
                "severity": "high" if ratio >= 3.0 else "medium",
                "timestamp": datetime.now().isoformat(),
            }

        return None

    except Exception as e:
        logger.warning(f"Volume surge [{ticker}] failed: {e}")
        return None


def fetch_news_sentiment(ticker: str) -> list[dict]:
    """Finnhub에서 뉴스 수집."""
    if not FINNHUB_API_KEY:
        return []

    try:
        import finnhub
        client = finnhub.Client(api_key=FINNHUB_API_KEY)

        today = datetime.now()
        from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")

        news = client.company_news(ticker, _from=from_date, to=to_date)

        if not news:
            return []

        return [
            {
                "signal_type": "news",
                "ticker": ticker,
                "headline": n.get("headline", ""),
                "summary": n.get("summary", "")[:200],
                "source": n.get("source", ""),
                "url": n.get("url", ""),
                "datetime": datetime.fromtimestamp(n.get("datetime", 0)).isoformat(),
            }
            for n in news[:10]  # Latest 10
        ]

    except Exception as e:
        logger.warning(f"News [{ticker}] failed: {e}")
        return []


def collect_smart_money_signals(tickers: list[str]) -> dict:
    """
    복수 종목에 대해 스마트머니 신호 수집.

    Returns:
        {
            "insider_trades": [...],
            "volume_surges": [...],
            "short_interest": {...},
            "anomalies": [...]  # 이상 신호 요약
        }
    """
    all_insider = []
    all_surges = []
    all_short = {}
    anomalies = []

    for ticker in tickers:
        # Insider trades
        trades = fetch_insider_trades(ticker)
        if trades:
            all_insider.extend(trades)
            # Large insider buy = anomaly
            for t in trades:
                if t.get("value", 0) > 100000:  # $100K+
                    anomalies.append({
                        "signal_type": "insider_buy",
                        "ticker": ticker,
                        "description": f"{ticker} 내부자 매수 ${t['value']:,.0f} by {t['person']}",
                        "severity": "high" if t["value"] > 500000 else "medium",
                        "timestamp": t.get("date", datetime.now().isoformat()),
                    })

        # Volume surge
        surge = detect_volume_surge(ticker)
        if surge:
            all_surges.append(surge)
            anomalies.append({
                "signal_type": "volume_surge",
                "ticker": ticker,
                "description": f"{ticker} 거래량 {surge['surge_ratio']:.1f}x 급증",
                "severity": surge["severity"],
                "timestamp": surge["timestamp"],
            })

        # Short interest
        si = fetch_short_interest(ticker)
        if si:
            all_short[ticker] = si
            # Short interest 급감 = bullish signal
            if si["short_pct_float"] < 5.0:
                anomalies.append({
                    "signal_type": "low_short_interest",
                    "ticker": ticker,
                    "description": f"{ticker} 공매도 비율 낮음 ({si['short_pct_float']:.1f}%)",
                    "severity": "low",
                    "timestamp": si["timestamp"],
                })

    return {
        "insider_trades": all_insider,
        "volume_surges": all_surges,
        "short_interest": all_short,
        "anomalies": anomalies,
        "collected_at": datetime.now().isoformat(),
    }
