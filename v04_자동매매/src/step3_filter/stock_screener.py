"""
Step 3: 종목 1차 필터링.

Step 2에서 도출된 수혜 섹터 → 해당 섹터 내 종목 중 조건 충족하는 것만 추림.

필터 조건 (명세서 기준):
- 시가총액 $500M ~ $10B
- 거래량 20일 평균 대비 150%+
- 공매도 비율 낮을수록 가산
- 내부자 매수 최근 3일 내 → 가산
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import yfinance as yf

from src.utils.config import FILTERS

logger = logging.getLogger(__name__)

MIN_MCAP = FILTERS.get("market_cap_min", 500_000_000)
MAX_MCAP = FILTERS.get("market_cap_max", 10_000_000_000)
VOLUME_SURGE = FILTERS.get("volume_surge_threshold", 1.5)
MAX_RECENT_GAIN = FILTERS.get("max_recent_gain", 0.30)


def screen_single_stock(ticker: str) -> dict | None:
    """
    단일 종목 스크리닝. yfinance 기반.

    Returns:
        통과 시 종목 정보 dict, 미통과 시 None
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info

        if not info or not info.get("marketCap"):
            return None

        mcap = float(info.get("marketCap", 0))
        name = info.get("shortName") or info.get("longName") or ticker
        sector = info.get("sector", "Unknown")
        industry = info.get("industry", "Unknown")
        current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)

        # Pass/Fail: Market cap
        if mcap < MIN_MCAP or mcap > MAX_MCAP:
            logger.debug(f"[{ticker}] FAIL: mcap ${mcap/1e6:.0f}M")
            return None

        # Volume surge check
        hist = t.history(period="1mo")
        if hist is None or len(hist) < 5:
            return None

        avg_volume = hist["Volume"].iloc[:-1].mean()
        latest_volume = hist["Volume"].iloc[-1]
        volume_ratio = (latest_volume / avg_volume) if avg_volume > 0 else 0

        # Recent price gain check (exclude 30%+ gainers)
        if len(hist) >= 20:
            price_20d_ago = hist["Close"].iloc[-20]
            recent_gain = (current_price - price_20d_ago) / price_20d_ago
            if recent_gain > MAX_RECENT_GAIN:
                logger.debug(f"[{ticker}] FAIL: recent gain {recent_gain:.1%}")
                return None

        # Short interest
        short_pct = float(info.get("shortPercentOfFloat", 0) or 0) * 100

        # Institutional ownership
        inst_pct = float(info.get("heldPercentInstitutions", 0) or 0) * 100

        # Daily traded value
        avg_daily_value = (avg_volume * current_price) if current_price else 0

        return {
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "industry": industry,
            "market_cap": mcap,
            "current_price": current_price,
            "avg_daily_value": avg_daily_value,
            "volume_ratio": round(volume_ratio, 2),
            "short_pct": round(short_pct, 2),
            "institutional_pct": round(inst_pct, 2),
            "passed": True,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.warning(f"[{ticker}] Screen failed: {e}")
        return None


def screen_sector_stocks(
    sector_keywords: list[str],
    candidate_tickers: list[str] | None = None,
    max_workers: int = 10,
) -> list[dict]:
    """
    섹터 키워드에 해당하는 종목들을 스크리닝.

    Args:
        sector_keywords: Step 2에서 도출된 수혜 섹터 리스트
        candidate_tickers: 후보 종목 리스트 (없으면 AI가 찾아야 함)
        max_workers: 병렬 처리 워커 수

    Returns:
        필터 통과한 종목 리스트
    """
    if not candidate_tickers:
        logger.warning("No candidate tickers provided")
        return []

    passed: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(screen_single_stock, ticker): ticker
            for ticker in candidate_tickers
        }

        for future in as_completed(futures):
            ticker = futures[future]
            try:
                result = future.result()
                if result:
                    passed.append(result)
                    logger.info(
                        f"  PASS: {ticker} — mcap ${result['market_cap']/1e6:.0f}M, "
                        f"vol {result['volume_ratio']:.1f}x, short {result['short_pct']:.1f}%"
                    )
            except Exception as e:
                logger.error(f"[{ticker}] Exception: {e}")

    # Sort by volume_ratio (highest first)
    passed.sort(key=lambda x: x["volume_ratio"], reverse=True)

    logger.info(f"Screened {len(passed)}/{len(candidate_tickers)} passed")
    return passed


def discover_tickers_for_sectors(
    sectors: list[str],
    max_per_sector: int = 15,
) -> list[str]:
    """
    Gemini를 사용해 섹터별 후보 종목을 발굴.
    Step 2에서 수혜 섹터가 나오면 이 함수로 구체적 종목을 찾음.
    """
    from src.utils.gemini_client import generate_json

    if not sectors:
        return []

    prompt = f"""Find US-listed stocks for each of these sectors.
Requirements:
- Market cap: $500M to $10B
- US-listed on NYSE or NASDAQ
- Actively traded, not OTC/pink sheets

Sectors: {', '.join(sectors)}

Return a JSON array of ticker symbols only (no other text):
["TICKER1", "TICKER2", "TICKER3", ...]

Return up to {max_per_sector} tickers per sector, {max_per_sector * len(sectors)} total max."""

    try:
        result = generate_json(prompt, temperature=0.2)
        if isinstance(result, list):
            # Flatten and deduplicate
            tickers = list(set(str(t).upper() for t in result if isinstance(t, str)))
            logger.info(f"Discovered {len(tickers)} tickers for {len(sectors)} sectors")
            return tickers
        return []
    except Exception as e:
        logger.error(f"Ticker discovery failed: {e}")
        return []
