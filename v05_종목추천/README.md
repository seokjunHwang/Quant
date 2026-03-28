# v05 종목추천 파이프라인

매일 06:30 KST — 국장(KOSPI/KOSDAQ) + 미장(NYSE/NASDAQ) 단타/스윙 후보 종목 자동 추천

---

## 전체 플로우

```
┌─────────────────────────────────────────────────────────────────────┐
│  매일 06:30 KST  python main.py --market all                        │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
          ╔════════════════▼════════════════╗
          ║  STEP 1   데이터 수집            ║
          ╠═════════════════════════════════╣
          ║  🔍 Gemini Google Search         ║  국장/미장 뉴스
          ║  📈 yfinance                     ║  VIX, S&P500, 환율, 금, 유가
          ║  🏛  DART API                    ║  오늘 공시 (참고용)
          ╚════════════════╤════════════════╝
                           │ news_data + macro_data
          ╔════════════════▼════════════════╗
          ║  STEP 2   테마 분석              ║
          ╠═════════════════════════════════╣
          ║  🤖 Claude CLI                   ║  뉴스+매크로 → 유효 테마 3~5개
          ║                                 ║  강도/지속기간/수혜섹터/리스크
          ╚════════════════╤════════════════╝
                           │ themes (강/중/약 + 후보 종목 힌트)
          ╔════════════════▼════════════════╗
          ║  STEP 3   종목 리서치 + 필터링   ║
          ╠═════════════════════════════════╣
          ║  🏛  DART 리스크 개별 체크        ║  후보 종목만 유상증자/보호예수 조회
          ║  🔍 Gemini Google Search         ║  종목별 호재/악재/뉴스 (최대 40종목)
          ║  🏛  DART 재무 (국장만)          ║  부채비율 · 영업이익률 · 현금
          ╚════════════════╤════════════════╝
                           │ 후보 종목 + 리서치 결과 (scored)
          ╔════════════════▼════════════════╗
          ║  STEP 4   차트 분석              ║
          ╠═════════════════════════════════╣
          ║  📊 pykrx / yfinance             ║  OHLCV 60일치 수집
          ║  🐍 Python                       ║  RSI · 볼린저밴드 · MACD · 거래량비율
          ║  🤖 Claude CLI                   ║  지표 해석 → 매매 타이밍 (최대 30종목)
          ╚════════════════╤════════════════╝
                           │ 차트 점수 + 진입조건 + 손절기준
          ╔════════════════▼════════════════╗
          ║  STEP 5   최종 점수 + 리포트     ║
          ╠═════════════════════════════════╣
          ║  🐍 Python 점수 계산             ║  테마(30) + 차트(30) + 수급(20) + 재무(20)
          ║  🤖 Claude CLI                   ║  투자 리포트 생성 (왜 이 종목인지)
          ╚════════════════╤════════════════╝
                           │
          ┌────────────────▼────────────────┐
          │  📄 final_report_YYYYMMDD.md     │  최종 추천 15종목
          │     대형주 5개 + 중소형주 10개    │  진입전략 · 손절 · 목표가
          └─────────────────────────────────┘
```

---

## AI 호출 구조

| 단계 | 도구 | 역할 | 횟수 |
|------|------|------|------|
| Step 1 | **Gemini + Google Search** | 실시간 뉴스 검색 | 3회 |
| Step 2 | **Claude CLI** | 테마 추론/판단 | 1회 |
| Step 3 | **Gemini + Google Search** | 종목별 뉴스 검색 | 최대 40회 |
| Step 4 | **Claude CLI** | 차트 해석/타이밍 | 최대 30회 |
| Step 5 | **Claude CLI** | 리포트 작성 | 1회 |

> Gemini → 검색이 필요한 곳 (실시간 정보)
> Claude → 추론이 필요한 곳 (판단·분석·글쓰기)

---

## 디렉토리 구조

```
v05_종목추천/
├── main.py                        # 즉시 실행 오케스트레이터
├── main_schedule.py               # 자동 실행 스케줄러 (매일 06:30 KST)
├── config/
│   ├── api_keys.env               # GEMINI_API_KEY, DART_API_KEY
│   └── settings.yaml              # 가중치, 필터 기준
├── src/
│   ├── utils/
│   │   ├── gemini_client.py       # Gemini API 래퍼 (검색 로깅 포함)
│   │   ├── claude_cli.py          # Claude CLI subprocess 래퍼
│   │   └── config.py              # 설정 로더
│   ├── step1_collect/
│   │   ├── news_gemini.py         # 🔍 Gemini Search — 시장 뉴스
│   │   ├── market_data.py         # 📈 yfinance/pykrx — OHLCV·매크로
│   │   └── dart.py                # 🏛  DART API — 공시 리스크
│   ├── step2_theme/
│   │   └── theme_claude.py        # 🤖 Claude CLI — 테마 분석
│   ├── step3_research/
│   │   ├── stock_gemini.py        # 🔍 Gemini Search — 종목 리서치
│   │   ├── financial.py           # 🏛  DART — 재무 데이터
│   │   └── filter.py              # ✂️  필터링 + 점수 + 저장
│   ├── step4_chart/
│   │   ├── indicators.py          # 🐍 RSI·BB·MACD 계산
│   │   └── chart_claude.py        # 🤖 Claude CLI — 차트 해석
│   └── step5_score/
│       ├── scorer.py              # 🐍 종합 점수 계산
│       └── report_claude.py       # 🤖 Claude CLI — 리포트 생성
└── data/
    ├── YYYYMMDD/
    │   └── all/                          # (또는 kr/ us/)
    │       ├── step1_데이터수집/
    │       │   ├── step1.json            # 캐시
    │       │   └── step1_summary.md
    │       ├── step2_테마분석/
    │       │   ├── step2.json
    │       │   └── step2_themes.md
    │       ├── step3_종목필터링/
    │       │   ├── step3.json
    │       │   ├── step3_filter.json
    │       │   └── step3_filter.md       # 제외 종목 사유
    │       ├── step4_차트분석/
    │       │   └── step4.json
    │       └── step5_리포트/
    │           ├── final_report_*.json
    │           └── final_report_*.md     # ← 최종 리포트
    └── logs/
        ├── search_usage.jsonl            # Gemini 검색 횟수 추적
        └── claude_usage.jsonl            # Claude 사용 추적
```

---

## 빠른 시작

```bash
# 패키지 설치
pip install -r requirements.txt

# Claude CLI 로그인 (최초 1회)
claude auth login
```

### 즉시 실행
```bash
python main.py                  # 전체 시장
python main.py --market kr      # 국장만
python main.py --market us      # 미장만
python main.py --from step3     # step3부터 재실행 (캐시 활용)
python main.py --dry-run        # AI 없이 데이터 수집만 테스트
```

### 자동 실행 — 매일 06:30 KST (평일)
```bash
python main_schedule.py         # 실행 후 다음 06:30 KST까지 대기 → 자동 실행
python main_schedule.py --market kr
```
> 종료: `Ctrl+C`

---

## 점수 가중치

```
종합점수 = 테마관련성(30%) + 차트(30%) + 수급(20%) + 재무(20%)
         - DART 패널티 (유상증자 -30 / 보호예수 -20)
```

## 최종 출력 — 최대 30종목 (국장 10 + 미장 20)

```
국장:  대형  3개 + 중소형  7개 = 10개
미장:  대형  8개 + 중소형 12개 = 20개
```

각 종목마다: 진입 조건 · 손절 기준 · 목표가 · 주요 리스크 · 향후 일정

---

## cron 자동 실행 (평일 06:30 KST)

```bash
30 6 * * 1-5 cd /workspace/Quant/v05_종목추천 && python main.py >> /tmp/v05_$(date +\%Y\%m\%d).log 2>&1
```
