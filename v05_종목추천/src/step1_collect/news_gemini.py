from __future__ import annotations
"""
Step 1-1: Gemini Google Search로 뉴스 수집.
국장/미장 당일 주요 뉴스 + 시장 환경 서칭.
"""

import logging
from src.utils.config import now_kst

from src.utils.gemini_client import generate_json

logger = logging.getLogger(__name__)

SYSTEM = """당신은 미국/한국 주식시장 전문 뉴스 분석가입니다.
실시간 뉴스를 검색하여 오늘 주식시장에 영향을 줄 정보를 JSON으로 정리합니다.
반드시 오늘 날짜 기준 최신 정보만 사용하세요."""


def fetch_market_news(market: str) -> dict:
    """
    미장(us) 또는 국장(kr) 뉴스 수집.

    Returns:
        {
            "market": "us" | "kr",
            "date": "YYYY-MM-DD",
            "macro_environment": {...},
            "hot_themes": [...],
            "sector_news": [...],
            "risk_factors": [...],
        }
    """
    today = now_kst().strftime("%Y년 %m월 %d일")
    market_name = "미국" if market == "us" else "한국"
    exchange = "NYSE/NASDAQ" if market == "us" else "KOSPI/KOSDAQ"

    prompt = f"""오늘({today}) {market_name} {exchange} 주식시장 분석을 위해 최신 뉴스를 검색하고 아래 JSON으로 반환해줘.

{{
  "market": "{market}",
  "date": "오늘 날짜",
  "macro_environment": {{
    "summary": "전반적 시장 분위기 한 문장",
    "key_indicators": [
      {{"name": "지표명", "value": "현재값", "trend": "상승/하락/보합", "impact": "시장에 미치는 영향"}}
    ]
  }},
  "hot_themes": [
    {{
      "theme": "테마명",
      "reason": "왜 오늘 핫한지",
      "trading_type": "단타/스윙/둘다",
      "sectors": ["관련 섹터1", "관련 섹터2"]
    }}
  ],
  "sector_news": [
    {{
      "sector": "섹터명",
      "direction": "bullish/bearish/neutral",
      "key_news": "핵심 뉴스 한 줄",
      "reason": "이유"
    }}
  ],
  "risk_factors": [
    {{"factor": "리스크 요인", "severity": "high/medium/low", "description": "설명"}}
  ]
}}

규칙:
- hot_themes는 3~5개
- sector_news는 오늘 움직임 있는 섹터만
- 실제 검색된 최신 뉴스 기반으로 작성
- 없으면 빈 배열 []"""

    logger.info(f"Fetching {market_name} market news via Gemini Search...")
    result = generate_json(
        prompt,
        system_instruction=SYSTEM,
        temperature=0.2,
        use_search=True,
        search_context=f"step1_news_{market}",
    )
    return result


def fetch_us_premarket() -> dict:
    """미장 프리마켓 + 전날 종가 기준 주요 이슈."""
    today = now_kst().strftime("%Y년 %m월 %d일")

    prompt = f"""오늘({today}) 미국 주식 프리마켓 및 전날 종가 기준 주요 이슈를 검색해서 JSON으로 반환해줘.

{{
  "premarket_movers": [
    {{"ticker": "티커", "name": "종목명", "change_pct": 등락률숫자, "reason": "이유"}}
  ],
  "earnings_today": [
    {{"ticker": "티커", "name": "종목명", "expectation": "예상 EPS", "impact": "예상 시장 반응"}}
  ],
  "economic_events": [
    {{"time_et": "발표시간(ET)", "event": "이벤트명", "forecast": "예상치", "importance": "high/medium/low"}}
  ],
  "fed_watch": {{
    "current_rate": "현재 금리",
    "next_meeting": "다음 FOMC 날짜",
    "cut_probability": "금리인하 확률 (%)"
  }}
}}"""

    result = generate_json(
        prompt,
        temperature=0.2,
        use_search=True,
        search_context="step1_us_premarket",
    )
    return result
