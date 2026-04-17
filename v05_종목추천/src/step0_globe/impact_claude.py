from __future__ import annotations
"""
Step 0-2: Claude CLI로 이벤트 영향 분석 + 좌표 매핑.
이벤트 → 수혜/피해 섹터 → 종목 연결 + 지도 좌표.
"""

import json
import logging

from src.utils.claude_cli import ask_claude

logger = logging.getLogger(__name__)

# 주요 도시/지역 좌표 (하드코딩 — API 불필요)
COORDS = {
    "미국": {"lat": 38.9, "lng": -77.0, "city": "워싱턴"},
    "뉴욕": {"lat": 40.7, "lng": -74.0, "city": "뉴욕"},
    "LA": {"lat": 34.0, "lng": -118.2, "city": "LA"},
    "중국": {"lat": 39.9, "lng": 116.4, "city": "베이징"},
    "일본": {"lat": 35.7, "lng": 139.7, "city": "도쿄"},
    "한국": {"lat": 37.5, "lng": 127.0, "city": "서울"},
    "대만": {"lat": 25.0, "lng": 121.5, "city": "타이베이"},
    "이란": {"lat": 35.7, "lng": 51.4, "city": "테헤란"},
    "이스라엘": {"lat": 31.8, "lng": 35.2, "city": "예루살렘"},
    "사우디": {"lat": 24.7, "lng": 46.7, "city": "리야드"},
    "사우디아라비아": {"lat": 24.7, "lng": 46.7, "city": "리야드"},
    "UAE": {"lat": 24.5, "lng": 54.4, "city": "아부다비"},
    "러시아": {"lat": 55.8, "lng": 37.6, "city": "모스크바"},
    "우크라이나": {"lat": 50.4, "lng": 30.5, "city": "키이우"},
    "영국": {"lat": 51.5, "lng": -0.1, "city": "런던"},
    "독일": {"lat": 52.5, "lng": 13.4, "city": "베를린"},
    "프랑스": {"lat": 48.9, "lng": 2.3, "city": "파리"},
    "유럽": {"lat": 50.8, "lng": 4.4, "city": "브뤼셀"},
    "인도": {"lat": 28.6, "lng": 77.2, "city": "뉴델리"},
    "호주": {"lat": -33.9, "lng": 151.2, "city": "시드니"},
    "브라질": {"lat": -15.8, "lng": -47.9, "city": "브라질리아"},
    "멕시코": {"lat": 19.4, "lng": -99.1, "city": "멕시코시티"},
    "캐나다": {"lat": 45.4, "lng": -75.7, "city": "오타와"},
    "북한": {"lat": 39.0, "lng": 125.8, "city": "평양"},
    "칠레": {"lat": -33.4, "lng": -70.6, "city": "산티아고"},
    "호르무즈": {"lat": 26.5, "lng": 56.3, "city": "호르무즈해협"},
    "수에즈": {"lat": 30.0, "lng": 32.6, "city": "수에즈운하"},
    "NYSE": {"lat": 40.7, "lng": -74.0, "city": "NYSE"},
    "KRX": {"lat": 37.5, "lng": 127.0, "city": "KRX"},
}


def _get_coords(country: str) -> dict:
    """국가/지역명으로 좌표 반환."""
    for key, val in COORDS.items():
        if key in country or country in key:
            return val
    return {"lat": 0, "lng": 0, "city": country}


def analyze_events_impact(
    events_data: dict,
    calendar_data: dict,
    themes_data: dict | None = None,
) -> dict:
    """
    Claude CLI로 이벤트 영향 분석.
    - 이벤트별 수혜/피해 섹터 + 종목 매핑
    - 이벤트간 연결 관계 (멀티포인트)
    - 지도 좌표 부여

    Args:
        events_data: step0 fetch_global_events 결과
        calendar_data: step0 fetch_economic_calendar 결과
        themes_data: step2 테마 분석 결과 (있으면 추천 종목과 교차)
    """
    events = events_data.get("events", [])
    calendar = calendar_data.get("calendar", [])

    # 추천 종목 리스트 (있으면)
    picks_text = ""
    if themes_data:
        picks = []
        for t in themes_data.get("themes", []):
            for hint in t.get("tickers_hint_us", []) + t.get("tickers_hint_kr", []):
                picks.append(hint)
        if picks:
            picks_text = f"\n\n현재 추천 후보 종목: {', '.join(picks[:30])}"

    events_json = json.dumps(events, ensure_ascii=False, indent=2)
    calendar_json = json.dumps(calendar[:15], ensure_ascii=False, indent=2)

    prompt = f"""너는 글로벌 거시 분석가다. 아래 이벤트와 캘린더를 종합해 주식시장 영향을
프론트엔드(글로벌 이벤트맵)가 그대로 사용할 JSON 한 덩어리로 출력한다.

=== 글로벌 이벤트 (오늘) ===
{events_json}

=== 경제 캘린더 (향후 2주) ===
{calendar_json}
{picks_text}

[출력 형식]
- 반드시 하나의 JSON 객체(dict)로만 출력하라. 배열로 감싸지 마라.
- 설명/마크다운/코드블록 없이 JSON 본문만.
- 최상위 키는 정확히 "events", "upcoming", "sector_summary" 세 개.
- events 는 5~10개, upcoming 은 캘린더 high/medium 만 5~10개, sector_summary 는 6~10개.

[필드 스키마]
{{
  "events": [
    {{
      "id": "ev_001",
      "title": "이벤트 제목",
      "summary": "2~3줄 요약 (구체 수치/이름 포함)",
      "severity": "critical/high/medium/low",
      "category": "war/policy/economic/energy/disaster/trade/technology/market",
      "status": "live/happened/developing/upcoming",
      "time_label": "3시간 전 / 오늘 09:00 / D-2 등",
      "points": [
        {{"country": "나라", "role": "origin/target/affected", "label": "이 점에서 무슨 일"}}
      ],
      "connections": [
        {{"from": "나라1", "to": "나라2", "type": "attack/trade/alliance/impact"}}
      ],
      "impact_chain": ["1차 → 2차", "2차 → 3차"],
      "affected_sectors": [
        {{"sector": "섹터명", "direction": "bullish/bearish", "magnitude": "+3~5%"}}
      ],
      "affected_tickers": [
        {{"ticker": "티커", "name": "종목명", "impact": "수혜/피해", "reason": "이유"}}
      ]
    }}
  ],
  "upcoming": [
    {{
      "date": "YYYY-MM-DD",
      "d_day": "D-2",
      "event": "이벤트명",
      "importance": "high/medium",
      "country": "나라",
      "category": "fed/economic/market",
      "scenarios": [
        {{"name": "비둘기(완화)", "probability": "60%", "impact": "성장주 수혜"}},
        {{"name": "매파(긴축)", "probability": "40%", "impact": "가치주 수혜"}}
      ],
      "watch_sectors": ["섹터1", "섹터2"]
    }}
  ],
  "sector_summary": [
    {{"sector": "섹터명", "net_direction": "bullish/bearish/neutral", "event_count": 2, "key_reason": "이유"}}
  ]
}}

[Few-shot 예시 — 이 형식과 디테일 수준을 그대로 따라라]
{{
  "events": [
    {{
      "id": "ev_001",
      "title": "중동 전쟁 격화 및 호르무즈 해협 봉쇄 지속",
      "summary": "미국·이스라엘의 이란 공습으로 중동 긴장 최고조. 호르무즈 해협 사실상 봉쇄로 글로벌 원유 공급 15% 차질, 국제 유가 배럴당 120달러 근접.",
      "severity": "critical",
      "category": "war",
      "status": "live",
      "time_label": "오늘 09:00 기준 (진행중)",
      "points": [
        {{"country": "이란", "role": "target", "label": "미·이스라엘 공습 대상, 해협 봉쇄 주체"}},
        {{"country": "이스라엘", "role": "origin", "label": "이란 공습 참여"}},
        {{"country": "미국", "role": "origin", "label": "이란 공습 주도"}},
        {{"country": "사우디아라비아", "role": "affected", "label": "원유 수출 경로 차질"}},
        {{"country": "UAE", "role": "affected", "label": "원유 수출 경로 차질"}}
      ],
      "connections": [
        {{"from": "미국", "to": "이란", "type": "attack"}},
        {{"from": "이스라엘", "to": "이란", "type": "attack"}},
        {{"from": "이란", "to": "사우디아라비아", "type": "impact"}},
        {{"from": "이란", "to": "UAE", "type": "impact"}},
        {{"from": "이란", "to": "한국", "type": "impact"}}
      ],
      "impact_chain": [
        "호르무즈 해협 봉쇄 → 글로벌 원유 공급 15% 차질 → 국제 유가 120달러 근접",
        "유가 급등 → 정유·E&P 기업 마진 확대 → 정유주 강세",
        "고유가 → 항공·해운 연료비 부담 → 항공주 약세"
      ],
      "affected_sectors": [
        {{"sector": "에너지(E&P·정유)", "direction": "bullish", "magnitude": "+5~8%"}},
        {{"sector": "방위산업", "direction": "bullish", "magnitude": "+3~5%"}},
        {{"sector": "항공·해운", "direction": "bearish", "magnitude": "-2~4%"}}
      ],
      "affected_tickers": [
        {{"ticker": "XOM", "name": "엑슨모빌", "impact": "수혜", "reason": "유가 급등 시 마진 직접 확대"}},
        {{"ticker": "LMT", "name": "록히드마틴", "impact": "수혜", "reason": "방산 수요·미사일 보충 수주"}},
        {{"ticker": "DAL", "name": "델타항공", "impact": "피해", "reason": "제트유 비용 급증"}}
      ]
    }}
  ],
  "upcoming": [
    {{
      "date": "2026-04-15",
      "d_day": "D-8",
      "event": "미국 3월 CPI 발표",
      "importance": "high",
      "country": "미국",
      "category": "economic",
      "scenarios": [
        {{"name": "예상 하회 (둔화)", "probability": "55%", "impact": "금리 인하 기대 → 성장·기술주 강세"}},
        {{"name": "예상 상회 (재점화)", "probability": "45%", "impact": "긴축 우려 → 금융·가치주 우위"}}
      ],
      "watch_sectors": ["반도체", "성장 기술주", "금융"]
    }}
  ],
  "sector_summary": [
    {{
      "sector": "에너지(E&P·정유)",
      "net_direction": "bullish",
      "event_count": 2,
      "key_reason": "호르무즈 봉쇄로 유가 120달러 근접, OPEC+ 증산도 실효성 부족"
    }},
    {{
      "sector": "방위산업",
      "net_direction": "bullish",
      "event_count": 1,
      "key_reason": "중동 충돌 격화로 방산 발주 모멘텀 강화"
    }},
    {{
      "sector": "항공·해운",
      "net_direction": "bearish",
      "event_count": 1,
      "key_reason": "고유가로 연료비 부담 가중, 운임 전가 한계"
    }}
  ]
}}

[작성 규칙]
- 위 예시는 형식 참고용이다. 실제 입력된 오늘의 이벤트/캘린더를 바탕으로 새로 작성하라.
- events 는 severity/시장영향 중요도 순으로 정렬.
- connections 는 여러 나라에 걸치는 이벤트(전쟁/무역분쟁/공급망)에서만 만들고, 단일 국가 이벤트는 빈 배열.
- upcoming 은 경제 캘린더에서 importance high/medium 만 골라 시나리오 2개씩.
- sector_summary 는 events 전체를 종합해 오늘 유리/불리 섹터를 6~10개 정리.
- affected_tickers 는 실제 직접 영향이 명확한 것만. 억지로 채우지 말 것 (없으면 빈 배열).
- 입력 데이터에 없는 사실을 만들지 말 것. 추정은 impact_chain/scenarios 에만."""

    logger.info("Analyzing event impacts via Claude CLI (Opus 4.6)...")
    result = ask_claude(
        prompt,
        expect_json=True,
        allow_search=True,
        timeout=900,
        context="step0_impact_analysis",
        model="claude-opus-4-6",  # 대규모 종합 분석은 Opus가 안정적
    )

    # Sonnet/Opus 가 가끔 [{...}] 형태로 한 번 더 감싸는 경우 풀어준다
    if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
        result = result[0]

    # 좌표 매핑
    if isinstance(result, dict):
        for event in result.get("events", []):
            for point in event.get("points", []):
                coords = _get_coords(point.get("country", ""))
                point["lat"] = coords["lat"]
                point["lng"] = coords["lng"]
                point.setdefault("city", coords["city"])

            for conn in event.get("connections", []):
                from_coords = _get_coords(conn.get("from", ""))
                to_coords = _get_coords(conn.get("to", ""))
                conn["from_lat"] = from_coords["lat"]
                conn["from_lng"] = from_coords["lng"]
                conn["to_lat"] = to_coords["lat"]
                conn["to_lng"] = to_coords["lng"]

        for item in result.get("upcoming", []):
            coords = _get_coords(item.get("country", ""))
            item["lat"] = coords["lat"]
            item["lng"] = coords["lng"]

    return result if isinstance(result, dict) else {}
