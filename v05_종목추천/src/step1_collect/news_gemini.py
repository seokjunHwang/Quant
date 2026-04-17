from __future__ import annotations
"""
Step 1-1: Gemini Google Search로 뉴스 수집.
국장/미장 당일 주요 뉴스 + 시장 환경 서칭.
"""

import logging
from src.utils.config import now_kst

from src.utils.gemini_client import generate_json
from src.utils.config import GEMINI_FALLBACK_MODEL

logger = logging.getLogger(__name__)

SYSTEM = """당신은 미국/한국 주식시장 전문 뉴스 분석가입니다.
실시간 뉴스를 검색하여 오늘 주식시장에 영향을 줄 정보를 JSON으로 정리합니다.

검색 규칙:
- 반드시 오늘 날짜 또는 최근 24시간 이내 뉴스만 사용
- 여러 번 검색하여 다양한 소스 확인 (Reuters, Bloomberg, 연합뉴스, 한경, 매경 등)
- 장전/장후 뉴스, 해외 시장 영향, 정책 발표, 기업 실적 모두 포함
- 출처가 불분명하거나 날짜가 오래된 정보는 제외"""


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
    now = now_kst()
    today = now.strftime("%Y년 %m월 %d일")
    current_time = now.strftime("%H시 %M분")
    market_name = "미국" if market == "us" else "한국"
    exchange = "NYSE/NASDAQ" if market == "us" else "KOSPI/KOSDAQ"

    prompt = f"""현재 시각: {today} {current_time} (한국시간 KST)

{market_name} {exchange} 주식시장에 영향을 줄 최신 뉴스를 검색해줘.
지금 이 시각 기준으로 가장 최신 뉴스를 찾아야 한다. 몇 시간 전, 심지어 몇 분 전에 나온 속보도 포함해야 한다.

다음 키워드로 각각 검색해서 종합해줘:
1. "{market_name} 주식시장 오늘 {today}" — 시장 전반 분위기
2. "{exchange} 테마 급등 {today}" — 오늘 핫한 테마/섹터
3. "{market_name} 경제 정책 금리 {today}" — 매크로/정책 이슈
4. "{market_name} 기업 실적 공시 {today}" — 실적/공시 뉴스
5. "{market_name} 주식 리스크 악재 {today}" — 리스크 요인
6. "breaking news stock market today" — 글로벌 속보 (지정학, 전쟁, 재난 등)

검색 결과를 아래 JSON으로 정리:
{{
  "market": "{market}",
  "date": "{today}",
  "macro_environment": {{
    "summary": "전반적 시장 분위기 한 문장",
    "key_indicators": [
      {{"name": "지표명", "value": "현재값", "trend": "상승/하락/보합", "impact": "시장에 미치는 영향"}}
    ]
  }},
  "hot_themes": [
    {{
      "theme": "테마명",
      "reason": "왜 오늘 핫한지 (출처/근거 포함)",
      "trading_type": "단타/스윙/둘다",
      "sectors": ["관련 섹터1", "관련 섹터2"]
    }}
  ],
  "sector_news": [
    {{
      "sector": "섹터명",
      "direction": "bullish/bearish/neutral",
      "key_news": "핵심 뉴스 한 줄 (출처 포함)",
      "reason": "이유"
    }}
  ],
  "risk_factors": [
    {{"factor": "리스크 요인", "severity": "high/medium/low", "description": "설명 (출처 포함)"}}
  ]
}}

규칙:
- hot_themes는 3~7개, 구체적 근거와 함께
- sector_news는 오늘 실제 움직임 있는 섹터만
- 반드시 오늘({today}) 또는 최근 24시간 이내 뉴스만 사용
- 속보/긴급 뉴스(지정학 충돌, 대형 정책 변경, 시장 급변 등)가 있으면 반드시 최우선 포함
- 각 항목에 뉴스 출처나 근거를 간략히 포함
- 없으면 빈 배열 []"""

    logger.info(f"Fetching {market_name} market news via Gemini Search...")
    result = generate_json(
        prompt,
        system_instruction=SYSTEM,
        temperature=0.2,
        use_search=True,
        search_context=f"step1_news_{market}",
        model=GEMINI_FALLBACK_MODEL,
    )
    # Gemini가 [{...}] 리스트로 감싸서 반환하는 경우 방어
    if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
        result = result[0]
    return result


def fetch_us_premarket() -> dict:
    """미장 프리마켓 + 전날 종가 기준 주요 이슈."""
    now = now_kst()
    today = now.strftime("%Y년 %m월 %d일")
    current_time = now.strftime("%H시 %M분")

    prompt = f"""현재 시각: {today} {current_time} (한국시간 KST)

다음을 각각 검색해줘 (가장 최신 정보 기준):
1. "US stock premarket movers today" — 프리마켓 급등/급락 종목
2. "earnings report today {today}" — 오늘 실적 발표 예정 종목
3. "economic calendar today" — 오늘 경제지표 발표 일정
4. "Fed interest rate watch" — 금리 전망

검색 결과를 아래 JSON으로 정리:

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
        model=GEMINI_FALLBACK_MODEL,
    )
    # Gemini가 [{...}] 리스트로 감싸서 반환하는 경우 방어
    if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
        result = result[0]
    return result
