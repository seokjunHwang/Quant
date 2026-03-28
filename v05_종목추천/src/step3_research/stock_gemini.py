from __future__ import annotations
"""
Step 3-1: Gemini Google Search로 개별 종목 리서치.
테마 후보 종목들에 대해 호재/악재/뉴스 수집.
"""

import logging
from src.utils.config import now_kst

from src.utils.gemini_client import generate_json

logger = logging.getLogger(__name__)


def research_stock(ticker: str, name: str, theme: str, market: str) -> dict:
    """
    개별 종목 Gemini 리서치.

    Args:
        ticker: 종목 코드
        name: 종목명
        theme: 연관 테마
        market: "kr" | "us"

    Returns:
        {
            "ticker": ...,
            "name": ...,
            "theme": ...,
            "catalysts": [...],
            "risks": [...],
            "news_summary": "...",
            "momentum": "bullish/bearish/neutral",
            "score_hint": 0~100,
        }
    """
    today = now_kst().strftime("%Y년 %m월 %d일")
    market_name = "한국" if market == "kr" else "미국"
    exchange = "KOSPI/KOSDAQ" if market == "kr" else "NYSE/NASDAQ"

    prompt = f"""오늘({today}) {market_name} {exchange} 종목 '{name}({ticker})' 에 대해 최신 뉴스를 검색하고 JSON으로 반환해줘.
이 종목은 '{theme}' 테마와 관련이 있다고 알려져 있음.

{{
  "ticker": "{ticker}",
  "name": "{name}",
  "theme": "{theme}",
  "catalysts": [
    {{"type": "호재/악재/중립", "content": "구체적 내용", "date": "날짜", "impact": "high/medium/low"}}
  ],
  "risks": [
    {{"type": "리스크 유형", "description": "설명", "severity": "high/medium/low"}}
  ],
  "news_summary": "최근 1주일 핵심 뉴스 2~3줄 요약",
  "momentum": "bullish/bearish/neutral",
  "analyst_view": "애널리스트 의견 또는 목표주가 (없으면 null)",
  "score_hint": 0~100
}}

규칙:
- catalysts는 실제 검색된 뉴스/공시 기반
- score_hint: 단타/스윙 관점에서 매매 매력도 (100이 최고)
- 정보 없으면 catalysts/risks 빈 배열, momentum은 neutral"""

    result = generate_json(
        prompt,
        temperature=0.1,
        use_search=True,
        search_context=f"step3_{market}_{ticker}",
    )

    # 필드 보정
    if isinstance(result, dict):
        result.setdefault("ticker", ticker)
        result.setdefault("name", name)
        result.setdefault("theme", theme)
        result.setdefault("catalysts", [])
        result.setdefault("risks", [])
        result.setdefault("news_summary", "")
        result.setdefault("momentum", "neutral")
        result.setdefault("score_hint", 50)
    else:
        result = {
            "ticker": ticker, "name": name, "theme": theme,
            "catalysts": [], "risks": [], "news_summary": "",
            "momentum": "neutral", "analyst_view": None, "score_hint": 50,
        }

    return result


def research_stocks_batch(
    candidates: list[dict],
    market: str,
    max_stocks: int = 30,
) -> list[dict]:
    """
    후보 종목 리스트를 순차 리서치.

    Args:
        candidates: [{"ticker": ..., "name": ..., "theme": ...}, ...]
        market: "kr" | "us"
        max_stocks: 최대 리서치 수 (검색 쿼리 절약)

    Returns:
        research_results: [research_stock() 결과, ...]
    """
    targets = candidates[:max_stocks]
    results = []

    for i, stock in enumerate(targets):
        ticker = stock.get("ticker", "")
        name = stock.get("name", ticker)
        theme = stock.get("theme", "")

        logger.info(f"  [{i+1}/{len(targets)}] {name}({ticker}) 리서치 중...")
        try:
            res = research_stock(ticker, name, theme, market)
            results.append(res)
        except Exception as e:
            logger.warning(f"  [{ticker}] 리서치 실패: {e}")
            results.append({
                "ticker": ticker, "name": name, "theme": theme,
                "catalysts": [], "risks": [], "news_summary": "",
                "momentum": "neutral", "analyst_view": None, "score_hint": 50,
                "error": str(e),
            })

    return results
