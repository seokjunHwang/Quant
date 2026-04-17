from __future__ import annotations
"""
Step 0-1: Gemini CLI(구독)로 글로벌 이벤트 수집.
지정학/경제/정책/자연재해/무역/기술 등 주가에 영향을 줄 이벤트.
3개 호출로 분야별 깊이 검색.

* 인증: gemini CLI OAuth 구독 (API key 불필요)
* 모델: gemini-3.1-pro-preview (Pro의 추론력으로 분석 정확도 ↑)
* 검색: CLI 내장 WebSearch/WebFetch 도구 자동 사용
* 호출수: data/logs/gemini_cli_usage.jsonl 에 누적 기록
"""

import logging

from src.utils.config import now_kst
from src.utils.gemini_cli import ask_gemini_cli

logger = logging.getLogger(__name__)


def _normalize(payload, key: str) -> list:
    """
    Gemini 응답이 dict({"events":[...]})이든 list([{...},{...}])이든
    [{...},{...}] 형태의 리스트로 반환한다.
    """
    if isinstance(payload, dict):
        return payload.get(key, []) or []
    if isinstance(payload, list):
        # 케이스 1: [{"events":[...]}]
        if len(payload) == 1 and isinstance(payload[0], dict) and key in payload[0]:
            return payload[0].get(key, []) or []
        # 케이스 2: [{...item}, {...item}, ...] (래퍼 누락)
        if all(isinstance(x, dict) and key not in x for x in payload):
            return payload
    return []

EVENT_JSON_SCHEMA = """{{
  "events": [
    {{
      "title": "이벤트 제목 (한글)",
      "summary": "2~3줄 요약 (한글, 구체적 수치/이름 포함)",
      "severity": "critical/high/medium/low",
      "category": "war/policy/economic/energy/disaster/trade/technology/supply_chain",
      "status": "live/happened/developing",
      "time_ago": "3시간 전 / 오늘 14:00 등",
      "source": "출처 (Reuters, AP, Bloomberg 등)",
      "countries": ["관련 국가1", "관련 국가2"],
      "impact_sectors": [
        {{"sector": "섹터명", "direction": "bullish/bearish", "reason": "이유 (구체적으로)"}}
      ]
    }}
  ]
}}"""

EVENT_RULES = """규칙:
- 주가에 섹터/종목 단위로 영향 예상되는 이벤트
- 48시간 이내 발생하거나 현재 진행중인 이벤트
- 구체적 수치, 인물명, 기업명 포함 (막연한 요약 금지)
- severity: critical(전면전/대형재해/긴급정책), high(정책/규제/대형사건), medium(지표/발언), low(참고)
- 이벤트 없으면 빈 배열"""


def fetch_global_events() -> dict:
    """글로벌 이벤트 수집 — 3회 호출로 분야별 깊이 검색."""
    now = now_kst()
    today = now.strftime("%Y년 %m월 %d일")
    current_time = now.strftime("%H시 %M분")

    all_events = []

    # ── 호출 1: 지정학 + 전쟁 + 군사 ────────────────────────
    prompt1 = f"""현재 시각: {today} {current_time} (한국시간 KST)

주식시장에 영향을 줄 수 있는 지정학/군사/안보 이벤트를 검색해줘.
지금 이 시각 기준 가장 최신 뉴스, 속보 포함.

다음 키워드로 각각 검색해서 종합:
1. "중동 전쟁 이란 이스라엘 미사일 공격 today" — 중동 분쟁
2. "러시아 우크라이나 전쟁 나토 escalation {today}" — 러우 전쟁
3. "대만 중국 해협 군사 긴장 Taiwan strait" — 대만해협
4. "북한 미사일 도발 핵 North Korea" — 북한 리스크
5. "US military defense spending NATO" — 미국/나토 군사 동향
6. "사우디 이란 중동 OPEC 석유 제재 sanction" — 중동 에너지 안보
7. "cyber attack infrastructure critical" — 사이버 공격/인프라 위협
8. "global arms deal defense contract" — 방산 계약/무기 수출

{EVENT_JSON_SCHEMA}

{EVENT_RULES}"""

    logger.info("  [1/3] 지정학/군사 이벤트 검색...")
    try:
        r1 = ask_gemini_cli(prompt1, expect_json=True, context="step0_geopolitical")
        all_events.extend(_normalize(r1, "events"))
    except Exception as e:
        logger.warning(f"  지정학 검색 실패: {e}")

    # ── 호출 2: 경제정책 + 무역 + 규제 ──────────────────────
    prompt2 = f"""현재 시각: {today} {current_time} (한국시간 KST)

주식시장에 영향을 줄 수 있는 경제정책/무역/규제 이벤트를 검색해줘.
지금 이 시각 기준 최신 뉴스.

다음 키워드로 각각 검색:
1. "미국 관세 tariff 중국 무역전쟁 trade war today" — 미중 무역
2. "반도체 수출규제 AI chip export ban" — 반도체/AI 규제
3. "Fed FOMC 파월 금리 interest rate today" — 연준 정책
4. "트럼프 바이든 행정명령 executive order" — 미국 대통령 정책
5. "한국 대통령 정책 발언 경제 today" — 한국 정부 정책
6. "중국 경기부양 stimulus 양회 정책" — 중국 경제 정책
7. "EU regulation 유럽 규제 탄소 디지털" — 유럽 규제
8. "일본 BOJ 엔화 금리 정책" — 일본 통화정책
9. "인도 제조업 이전 니어쇼어링 nearshoring" — 공급망 재편
10. "IPO 대형 상장 M&A 인수합병 today" — 기업 이벤트

{EVENT_JSON_SCHEMA}

{EVENT_RULES}"""

    logger.info("  [2/3] 경제정책/무역/규제 검색...")
    try:
        r2 = ask_gemini_cli(prompt2, expect_json=True, context="step0_policy_trade")
        all_events.extend(_normalize(r2, "events"))
    except Exception as e:
        logger.warning(f"  정책/무역 검색 실패: {e}")

    # ── 호출 3: 에너지/자원 + 자연재해 + 공급망 + 기술 ──────
    prompt3 = f"""현재 시각: {today} {current_time} (한국시간 KST)

주식시장에 영향을 줄 수 있는 에너지/자원/재해/기술 이벤트를 검색해줘.
지금 이 시각 기준 최신 뉴스.

다음 키워드로 각각 검색:
1. "OPEC 감산 원유 oil price production cut" — OPEC/원유
2. "천연가스 LNG 가스관 pipeline 가격" — 천연가스
3. "리튬 희토류 배터리 원자재 lithium rare earth" — 핵심 광물
4. "금 금값 gold price 안전자산" — 금/귀금속
5. "지진 earthquake tsunami today" — 지진/쓰나미
6. "산불 허리케인 홍수 wildfire hurricane flood" — 자연재해
7. "수에즈 호르무즈 해운 shipping 물류 disruption" — 해상 물류
8. "TSMC 삼성 반도체 파운드리 공장 semiconductor fab" — 반도체 공급
9. "AI 인공지능 규제 투자 데이터센터 GPU" — AI/기술
10. "신재생에너지 태양광 풍력 원전 nuclear energy" — 에너지전환
11. "바이오 FDA 승인 신약 clinical trial" — 바이오/제약

{EVENT_JSON_SCHEMA}

{EVENT_RULES}"""

    logger.info("  [3/3] 에너지/자원/재해/기술 검색...")
    try:
        r3 = ask_gemini_cli(prompt3, expect_json=True, context="step0_energy_tech")
        all_events.extend(_normalize(r3, "events"))
    except Exception as e:
        logger.warning(f"  에너지/기술 검색 실패: {e}")

    # 중복 제거 (title 기준)
    seen = set()
    deduped = []
    for ev in all_events:
        title = ev.get("title", "")
        if title and title not in seen:
            seen.add(title)
            deduped.append(ev)

    # severity 순 정렬
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    deduped.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 3))

    logger.info(f"  글로벌 이벤트 총 {len(deduped)}건 수집")
    return {"events": deduped}


def fetch_economic_calendar() -> dict:
    """향후 30일 주요 경제 캘린더 — 2회 호출 (미국+글로벌, 아시아)."""
    now = now_kst()
    today = now.strftime("%Y년 %m월 %d일")

    all_calendar = []

    # ── 호출 1: 미국 + 유럽 경제 캘린더 ─────────────────────
    prompt1 = f"""오늘({today}) 기준 향후 30일간 미국/유럽 주요 경제·시장 이벤트를 검색해서 JSON으로 반환해줘.

반드시 포함할 이벤트 유형:
- FOMC 금리결정, FOMC 의사록 공개, 파월 연설/기자회견
- 미국 CPI (소비자물가지수), PPI (생산자물가), Core PCE
- 비농업고용지표(NFP), 실업률, ADP 민간고용
- ISM 제조업 PMI, ISM 서비스업 PMI, 소비자신뢰지수
- 미국 GDP (속보/수정), 소매판매, 산업생산
- 4마녀의날(쿼드러플위칭), 월간옵션만기
- MSCI 리밸런싱, 러셀 리밸런싱
- 미국 국채 입찰 (10년물, 30년물)
- ECB 금리결정, ECB 총재 연설
- 미국 부채한도, 예산안 투표
- 빅테크 실적발표 (AAPL, MSFT, GOOG, AMZN, META, NVDA, TSLA)
- G7/G20 정상회담
- 대형 IPO

{{
  "calendar": [
    {{
      "date": "YYYY-MM-DD",
      "d_day": "D-3",
      "event": "이벤트명 (한글)",
      "category": "fed/economic/market/policy/earnings",
      "importance": "high/medium/low",
      "country": "미국/유럽",
      "impact_preview": "예상 영향 한 줄 (구체적으로)",
      "watch_sectors": ["영향받을 섹터"]
    }}
  ]
}}

규칙:
- 확인된 일정만 (추측 금지), 날짜순 정렬
- importance high: FOMC, CPI, NFP, 4마녀, MSCI, Core PCE, 빅테크실적
- importance medium: PPI, PMI, GDP, ECB, 소매판매, 국채입찰
- 최소 10개, 최대 25개"""

    logger.info("  [1/2] 미국/유럽 경제 캘린더 검색...")
    try:
        r1 = ask_gemini_cli(prompt1, expect_json=True, context="step0_calendar_us_eu")
        all_calendar.extend(_normalize(r1, "calendar"))
    except Exception as e:
        logger.warning(f"  미국/유럽 캘린더 실패: {e}")

    # ── 호출 2: 아시아 경제 캘린더 ───────────────────────────
    prompt2 = f"""오늘({today}) 기준 향후 30일간 아시아(한국/일본/중국) 주요 경제·시장 이벤트를 검색해서 JSON으로 반환해줘.

반드시 포함할 이벤트 유형:
- 한국 금통위(BOK) 금리결정
- 한국 수출입 동향, 국장 옵션만기, KOSPI200 선물만기
- 한국 대통령/정부 경제 관련 발언/정책
- 일본 BOJ 금리결정, 일본 CPI, 일본 GDP
- 중국 PMI (제조업/서비스), 중국 CPI, 중국 GDP
- 중국 양회, 국무원 정책 발표
- 중국 LPR 금리, 인민은행(PBOC) 정책
- 아시아 주요 IPO, 실적발표
- MSCI 한국/중국/일본 리밸런싱 영향

{{
  "calendar": [
    {{
      "date": "YYYY-MM-DD",
      "d_day": "D-3",
      "event": "이벤트명 (한글)",
      "category": "fed/economic/market/policy/earnings",
      "importance": "high/medium/low",
      "country": "한국/일본/중국",
      "impact_preview": "예상 영향 한 줄",
      "watch_sectors": ["영향받을 섹터"]
    }}
  ]
}}

규칙:
- 확인된 일정만, 날짜순 정렬
- importance high: BOK/BOJ 금리, 중국 PMI, 한국 수출, 옵션만기
- 최소 5개, 최대 15개"""

    logger.info("  [2/2] 아시아 경제 캘린더 검색...")
    try:
        r2 = ask_gemini_cli(prompt2, expect_json=True, context="step0_calendar_asia")
        all_calendar.extend(_normalize(r2, "calendar"))
    except Exception as e:
        logger.warning(f"  아시아 캘린더 실패: {e}")

    # 날짜순 정렬
    all_calendar.sort(key=lambda x: x.get("date", ""))

    logger.info(f"  경제 캘린더 총 {len(all_calendar)}건 수집")
    return {"calendar": all_calendar}
