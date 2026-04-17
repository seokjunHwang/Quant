# v05 종목추천 파이프라인

매일 06:30 KST — 국장(KOSPI/KOSDAQ) + 미장(NYSE/NASDAQ) 단타/스윙 후보 종목 자동 추천
+ 글로벌 이벤트맵 (지정학/경제 이슈 → 종목 영향 매핑)

---

## 시스템 구조도

```
┌────────────────────────────────────────────────────────────┐
│  v05_종목추천 파이프라인  (main.py 매일 06:30 KST 실행)     │
└────────────────────────────────────────────────────────────┘

[Step 0] 글로벌 이벤트
  ├─ events_gemini.py     🟦 Gemini CLI 구독 (Pro)        5 호출
  └─ impact_claude.py     🟪 Claude CLI 구독 (Sonnet)     1 호출
                              ↓
[Step 1] 데이터 수집
  ├─ news_gemini.py       🟨 Gemini API key (Flash)       2~4 호출
  ├─ market_data.py       📈 yfinance/pykrx               (외부 API)
  └─ dart.py              🏛  DART API                     (외부 API)
                              ↓
[Step 2] 테마 분석
  └─ theme_claude.py      🟪 Claude CLI 구독 (Sonnet)     1 호출
                              ↓
[Step 3] 종목 리서치 + 필터링
  ├─ stock_gemini_cli.py  🟦 Gemini CLI 구독 (Pro)        ~6 호출
  │                            5종목 배치 · 동시 2 · 캐시 · fallback
  ├─ filter.py / financial.py  🏛  DART/yfinance           (외부 API)
                              ↓
[Step 4] 차트 분석
  └─ chart_claude.py      🐍 코드 룰 채점                  0 호출
                              ↓
[Step 5] 최종 점수 + 리포트
  └─ report_claude.py     🟪 Claude CLI 구독 (Sonnet)     ~5 호출
                              ↓
                  📄 최종 리포트 (KR 5 + US 12)
                  🌍 글로벌 이벤트맵 데이터
```

### 인증 풀 (3개로 분리, 서로 영향 없음)

| 풀 | 인증 | 모델 | 한도 | 사용처 |
|---|---|---|---|---|
| 🟦 **Gemini CLI 구독** | OAuth | gemini-3.1-pro-preview | 1,500/일 | Step 0, Step 3 |
| 🟪 **Claude CLI 구독** | OAuth | claude-sonnet-4-6 | 구독 한도 | Step 0, 2, 5 |
| 🟨 **Gemini API key** | Key | gemini-3.1-flash-lite-preview | 검색 5,000/월 무료 | Step 1 (뉴스 검색) |

### 일일 호출 수 (KR 8 + US 18 = 26종목 기준)

| Step | 모듈 | 호출수 | 풀 |
|---|---|---|---|
| 0-1 | events_gemini (이벤트 3 + 캘린더 2) | **5** | 🟦 |
| 0-2 | impact_claude (영향 분석) | **1** | 🟪 |
| 1 | news_gemini (KR/US 뉴스) | **2~4** | 🟨 |
| 2 | theme_claude (테마 도출) | **1** | 🟪 |
| 3 | stock_gemini_cli (5종목 배치 × ~6) | **~6** | 🟦 |
| 4 | chart_claude (코드 채점) | **0** | — |
| 5 | report_claude (일정 검색 + 리포트) | **~5** | 🟪 |

> Gemini CLI 풀 사용량 ≈ **11 / 1,500 (0.7%)** — 매우 여유.
> Step 3 quota 잔량 < 30 시 자동 API key Flash로 fallback.

---

## 디렉토리 구조

```
v05_종목추천/
├── main.py                        # 종목추천 파이프라인 (Step 0~5)
├── server.py                      # FastAPI 웹서버
├── main_schedule.py               # 자동 실행 스케줄러 (매일 06:30 KST)
├── build_web.py                   # 웹 대시보드 데이터 빌드
├── config/
│   ├── api_keys.env               # GEMINI_API_KEY, DART_API_KEY
│   └── settings.yaml              # 가중치, 필터, 모델 설정
├── src/
│   ├── utils/
│   │   ├── gemini_cli.py          # 🟦 Gemini CLI 구독 래퍼 (호출수 누적)
│   │   ├── gemini_client.py       # 🟨 Gemini API key 래퍼
│   │   ├── claude_cli.py          # 🟪 Claude CLI 구독 래퍼 (Sonnet 4.6)
│   │   └── config.py
│   ├── step0_globe/               # 🌍 글로벌 이벤트맵
│   │   ├── events_gemini.py       # 🟦 글로벌 이벤트/캘린더 (CLI Pro)
│   │   └── impact_claude.py       # 🟪 영향 분석 + 좌표
│   ├── step1_collect/
│   │   ├── news_gemini.py         # 🟨 시장 뉴스 (API key Flash)
│   │   ├── market_data.py         # yfinance/pykrx — OHLCV·매크로
│   │   └── dart.py                # DART API — 공시 리스크
│   ├── step2_theme/
│   │   └── theme_claude.py        # 🟪 테마 분석
│   ├── step3_research/
│   │   ├── stock_gemini_cli.py    # 🟦 종목 리서치 (5종목 배치 + 캐시)
│   │   ├── stock_gemini.py        # 🟨 (구버전 fallback용)
│   │   ├── financial.py           # DART 재무
│   │   └── filter.py              # 필터링 + 점수
│   ├── step4_chart/
│   │   ├── indicators.py          # RSI/BB/MACD 계산
│   │   ├── chart_scorer.py        # 코드 룰 채점
│   │   └── chart_claude.py        # (래퍼만, AI 호출 없음)
│   └── step5_score/
│       ├── scorer.py
│       └── report_claude.py       # 🟪 최종 리포트
├── web/
│   ├── index.html                 # 대시보드 (글로벌맵/시장개요/종목추천/경제채널)
│   ├── css/  js/                  # 스타일·앱·글로벌맵(Leaflet)
│   └── data/                      # dates.json + YYYYMMDD.json + events_*.json
└── data/
    ├── YYYYMMDD/all/
    │   ├── step0_글로벌이벤트/
    │   ├── step1_데이터수집/
    │   ├── step2_테마분석/
    │   ├── step3_종목필터링/
    │   ├── step4_차트분석/
    │   └── step5_리포트/
    ├── cache/step3/YYYYMMDD/      # Step 3 종목 리서치 캐시 (당일만)
    └── logs/
        ├── gemini_cli_usage.jsonl # 🟦 CLI 구독 호출수
        ├── claude_usage.jsonl     # 🟪 Claude CLI 호출수 + 비용
        └── search_usage.jsonl     # 🟨 API key 검색쿼리 수
```

---

## 빠른 시작

```bash
# 패키지 설치
pip install -r requirements.txt
pip install fastapi uvicorn youtube-transcript-api httpx

# Claude CLI 로그인 (최초 1회) — Sonnet 4.6 사용
claude  # → /login → OAuth 브라우저 인증

# Gemini CLI 로그인 (최초 1회) — gemini-3.1-pro-preview 사용
gemini  # → Sign in with Google → OAuth 브라우저 인증
```

### 즉시 실행
```bash
python3.12 main.py                  # 전체 시장
python3.12 main.py --market kr      # 국장만
python3.12 main.py --market us      # 미장만
python3.12 main.py --from step0     # 글로벌 이벤트부터
python3.12 main.py --from step3     # step3부터 재실행 (캐시 활용)
python3.12 main.py --dry-run        # AI 없이 데이터 수집만 테스트
```

### 자동 실행 — 매일 06:30 KST (평일)
```bash
python3.12 main_schedule.py         # 다음 06:30 KST까지 대기 → 자동 실행
python3.12 main_schedule.py --market kr
```
> 종료: `Ctrl+C`

---

## 웹 대시보드 + API 서버

4개 탭: **글로벌맵** | **시장 개요** | **종목 추천** | **경제채널**

```bash
cd /workspace/Quant/v05_종목추천
python3.12 server.py &
cloudflared tunnel --url http://localhost:3001
```

| 탭 | 내용 |
|---|---|
| 글로벌맵 | Leaflet 다크맵 + 이벤트 마커 + 연결선 + 경제 타임라인 + 히트맵 |
| 시장 개요 | 매크로 지표 + 테마 + 뉴스 |
| 종목 추천 | 최종 17종목 테이블 (시총 포함) |
| 경제채널 | 유튜브 채널 영상 + AI 요약 (Gemini 무료) |

### API 엔드포인트

| 경로 | 설명 |
|---|---|
| `POST /api/youtube/summary` | 자막 추출 + Gemini 무료 AI 요약 |
| `GET /api/youtube/rss/{channel_id}` | YouTube RSS 프록시 (CORS 우회) |
| `GET /api/health` | 서버 상태 |
| `GET /api/docs` | Swagger UI |

---

## 점수 가중치

```
종합점수 = 테마관련성(30%) + 차트(30%) + 수급(20%) + 재무(20%)
         - DART 패널티 (유상증자 -30 / 보호예수 -20)
```

## 최종 출력 — 최대 17종목 (국장 5 + 미장 12)

```
국장:  대형  2개 + 중소형  3개 = 5개
미장:  대형  5개 + 중소형  7개 = 12개
```

각 종목마다: 시총 · 진입 조건 · 손절 기준 · 목표가 · 주요 리스크 · 향후 일정

---

## cron 자동 실행 (평일 06:30 KST)

```bash
30 6 * * 1-5 cd /workspace/Quant/v05_종목추천 && python3.12 main.py >> /tmp/v05_$(date +\%Y\%m\%d).log 2>&1
```
