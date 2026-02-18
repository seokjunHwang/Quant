# TradingView 자동매매 전략 생성 파이프라인 — 아키텍처 설계 프롬프트

## 🎯 프로젝트 목표

TradingView 커뮤니티에 공개된 수백~수천 개의 기술적 지표(Indicator) 및 전략(Strategy) 스크립트를 **자동으로 수집 → 분석 → 필터링 → 조합 → 백테스팅**하여, 수익률이 높은 자동매매 전략 후보군을 도출하는 **End-to-End 파이프라인**을 구축한다.

---

## 📋 프로젝트 개요

### 배경
- TradingView에는 커뮤니티가P 만든 수만 개의 Pine Script 기반 지표/전략이 공개되어 있다.
- 이 중 자동매매 알고리즘에 유의미한 신호를 생성하는 지표를 사람이 일일이 검토하는 것은 비현실적이다.
- 유망 지표들을 자동으로 선별하고, 다양한 조합으로 융합한 뒤, 각 조합의 수익성을 백테스팅으로 검증하는 자동화 시스템이 필요하다.

### 최종 산출물
1. **지표 데이터베이스**: 수집된 모든 지표의 메타데이터, Pine Script 원본, 분석 결과
2. **필터링된 유망 지표 목록**: 자동매매에 유의미하다고 판단된 지표들
3. **조합 전략 목록**: 유망 지표 2~4개를 융합한 복합 전략들
4. **백테스팅 결과 리포트**: 각 전략별 수익률, 샤프비율, MDD 등 성과 지표
5. **최종 랭킹**: 성과 기준 상위 전략 Top-N 리스트

---

## 🏗️ 시스템 아키텍처 (5단계 파이프라인)

```
[Stage 1: Collector] → [Stage 2: Analyzer] → [Stage 3: Filter] → [Stage 4: Combiner] → [Stage 5: Backtester]
      ↓                      ↓                     ↓                     ↓                      ↓
  Pine Scripts DB      Analysis Results       Shortlisted Set      Strategy Configs       Performance Reports
```

---

### Stage 1: 지표 수집기 (Collector)

#### 목적
TradingView 커뮤니티 스크립트에서 공개된 지표/전략의 Pine Script 소스코드와 메타데이터를 대량 수집한다.

#### 수집 대상
- TradingView 커뮤니티 스크립트 라이브러리 (https://www.tradingview.com/scripts/)
- 카테고리: Indicators, Strategies, Oscillators, Moving Averages, Volume, Volatility, Trend Analysis, Momentum 등
- 정렬 기준: Most Popular, Most Recent, Top Rated 등 복수 기준으로 수집

#### 수집 항목 (per script)
```json
{
  "script_id": "고유 식별자",
  "title": "스크립트 제목",
  "author": "작성자",
  "description": "설명",
  "category": ["카테고리 태그들"],
  "likes": 12345,
  "pine_version": "v5",
  "source_code": "Pine Script 전체 소스코드",
  "url": "원본 URL",
  "created_at": "생성일",
  "updated_at": "수정일",
  "collected_at": "수집 시점"
}
```

#### 기술 요구사항
- **크롤링 방식**: Playwright 또는 Selenium 기반 (TradingView는 SPA + 동적 렌더링)
- **로그인 처리**: TradingView 계정 로그인이 필요할 수 있음 (소스코드 열람 시)
- **Rate Limiting**: 요청 간 랜덤 딜레이 (3~8초), IP 차단 방지
- **재시도 로직**: 실패 시 exponential backoff
- **중복 방지**: script_id 기준 deduplication
- **저장**: SQLite 또는 JSON Lines 파일로 로컬 저장
- **목표 수량**: 최소 500개, 가능하면 2,000~5,000개

#### 대안 수집 경로 (크롤링이 차단될 경우)
- TradingView 공식 Pine Script 레퍼런스의 Built-in 지표 목록 활용
- GitHub에서 "tradingview pine script indicator" 검색하여 공개 저장소 수집
- 커뮤니티 포럼/블로그에서 공유된 Pine Script 코드 수집
- 주요 기술적 지표(RSI, MACD, BB, ATR, Stochastic 등)를 직접 Pine Script로 구현

---

### Stage 2: 지표 분석기 (Analyzer)

#### 목적
수집된 각 Pine Script를 파싱하여 구조를 이해하고, 자동매매 관점에서의 특성을 분류한다.

#### 분석 항목

##### 2-1. 코드 파싱 (정적 분석)
```yaml
parsed_info:
  pine_version: "v5"
  type: "indicator" | "strategy" | "library"
  inputs:                        # 사용자 조정 가능 파라미터
    - name: "length"
      type: "int"
      default: 14
  outputs:                       # plot, plotshape, alertcondition 등
    - type: "line"
      name: "RSI"
    - type: "signal"
      name: "overbought_cross"
  dependencies:                  # 사용하는 내장 함수/지표
    - "ta.rsi"
    - "ta.sma"
    - "ta.crossover"
  signal_generation:             # 매매 신호 생성 여부
    has_buy_signal: true
    has_sell_signal: true
    signal_type: "crossover"     # crossover, threshold, pattern 등
  complexity:
    lines_of_code: 85
    num_conditions: 6
    nested_depth: 3
```

##### 2-2. 의미 분석 (LLM 기반)
각 지표에 대해 LLM에 다음을 질의한다:

```
이 Pine Script 지표를 분석하여 다음을 판단하라:

1. 지표 유형 분류: [추세추종 / 모멘텀 / 변동성 / 거래량 / 패턴인식 / 지지저항 / 복합]
2. 시장 조건 적합성: [추세장 / 횡보장 / 변동성확대 / 전 시장 조건]
3. 타임프레임 적합성: [스캘핑(1-5분) / 데이트레이딩(15분-1시간) / 스윙(4시간-일봉) / 포지션(주봉+)]
4. 매매 신호 명확성 (1-10): 코드에서 명확한 진입/청산 신호를 추출할 수 있는가?
5. 다른 지표와의 조합 잠재력 (1-10): 독립적으로 쓰기보다 보조 지표로서 가치가 있는가?
6. 자동매매 적합도 종합 점수 (1-100)
7. 핵심 로직 요약 (3줄 이내)
8. Python 변환 난이도: [쉬움 / 보통 / 어려움 / 불가능]
9. 유사 지표 그룹: 이미 분석된 지표 중 로직이 90% 이상 겹치는 것이 있는지
```

#### 기술 요구사항
- **Pine Script 파서**: Python으로 기본 파서 구현 (정규식 + AST 수준)
  - `input.int()`, `input.float()`, `input.bool()` 등 파라미터 추출
  - `plot()`, `plotshape()`, `alertcondition()`, `strategy.entry()` 등 출력 추출
  - `ta.*` 함수 호출 추출
- **LLM 분석**: Anthropic Claude API 배치 호출
  - 비용 최적화: 먼저 짧은 요약 프롬프트로 1차 필터링 → 통과한 것만 상세 분석
  - 병렬 처리: asyncio + API rate limit 준수
- **결과 저장**: 각 지표별 분석 결과를 DB에 저장

---

### Stage 3: 필터링 엔진 (Filter)

#### 목적
분석 결과를 기반으로 자동매매 전략 구성에 유의미한 지표만 선별한다.

#### 필터링 기준

##### 1차 필터 (Hard Filter) — 자동 탈락 조건
- Pine Script 파싱 실패 (문법 오류, 불완전 코드)
- `type == "library"` (라이브러리는 단독 사용 불가)
- `signal_generation.has_buy_signal == false AND has_sell_signal == false` (신호 없음)
- `complexity.lines_of_code < 5` (너무 단순, 의미 없음)
- `python_conversion_difficulty == "불가능"`
- 유사 지표 그룹에서 likes가 가장 높은 것만 남기고 나머지 제거 (중복 제거)

##### 2차 필터 (Soft Filter) — 점수 기반 선별
- `자동매매_적합도_종합점수 >= 50`
- `매매_신호_명확성 >= 5`
- `조합_잠재력 >= 4`

##### 3차 분류 (Role Assignment)
통과한 지표를 역할별로 분류:
```yaml
roles:
  primary_signal:    # 주 매매 신호 생성 (진입/청산 판단)
    - 추세추종 지표
    - 모멘텀 지표
  confirmation:      # 보조 확인 신호
    - 거래량 지표
    - 변동성 지표
  filter:            # 시장 상태 필터 (매매 허용/금지)
    - 추세 강도 지표
    - 횡보 감지 지표
  exit:              # 청산 전용 신호
    - 과매수/과매도 감지
    - 변동성 기반 손절/익절
```

#### 산출물
- 유망 지표 N개 (목표: 30~100개)
- 각 지표별 역할 태그
- 조합 우선순위 점수

---

### Stage 4: 전략 조합기 (Combiner)

#### 목적
필터링된 지표들을 역할 기반으로 조합하여 복합 전략을 생성한다.

#### 조합 규칙

##### 전략 구조 (Strategy Template)
```python
class CompositeStrategy:
    primary_signal: Indicator      # 1개 (필수) — 진입 신호
    confirmation: List[Indicator]  # 0~2개 — 확인 신호
    market_filter: Indicator       # 0~1개 — 시장 상태 필터
    exit_signal: Indicator         # 0~1개 — 청산 신호 (없으면 primary의 반대 신호 사용)

    # 매매 로직
    def should_enter_long(self):
        return (
            self.primary_signal.buy_signal()
            and all(c.confirm_long() for c in self.confirmation)
            and self.market_filter.allow_trading()
        )

    def should_exit_long(self):
        return (
            self.exit_signal.exit_long()
            or self.primary_signal.sell_signal()
        )
```

##### 조합 생성 로직
```
1. primary_signal 풀에서 1개 선택
2. confirmation 풀에서 0~2개 선택 (조합)
3. market_filter 풀에서 0~1개 선택
4. exit_signal 풀에서 0~1개 선택
5. 각 지표의 주요 파라미터에 대해 2~3개 변형값 적용

총 경우의 수 = P × C(C,0~2) × F(0~1) × E(0~1) × 파라미터변형
```

##### 조합 수 제어
- 전수 조합은 비현실적이므로 **우선순위 기반 샘플링** 사용
- 1차: 고득점 지표 위주로 상위 조합 생성 (500~1,000개)
- 2차: 빠른 백테스팅으로 상위 20% 선별
- 3차: 선별된 조합에 대해 파라미터 그리드 서치 (최적화)

##### 조합 제약 조건
- 같은 카테고리의 지표를 primary + confirmation에 동시 사용 금지 (예: RSI + Stochastic 둘 다 모멘텀이므로 중복)
- 동일 base indicator 파생 지표 동시 사용 금지 (예: SMA 기반 지표 2개)
- 최소 2개, 최대 4개 지표로 구성

#### 산출물
```json
{
  "strategy_id": "STR_001",
  "components": {
    "primary": {"indicator_id": "IND_042", "params": {"length": 14}},
    "confirmation": [{"indicator_id": "IND_108", "params": {"period": 20}}],
    "filter": {"indicator_id": "IND_205", "params": {"threshold": 25}},
    "exit": null
  },
  "description": "RSI(14) 크로스오버 진입 + 볼린저밴드(20) 확인 + ADX(25) 추세필터"
}
```

---

### Stage 5: 백테스팅 엔진 (Backtester)

#### 목적
생성된 각 전략에 대해 과거 데이터로 성과를 측정하고 랭킹한다.

#### 백테스팅 프레임워크
- **1차 추천**: `vectorbt` (벡터화 연산, 수천 개 전략 동시 테스트 가능)
- **2차 추천**: `backtrader` (더 유연하지만 속도 느림)
- **보조**: `pandas-ta` (기술적 지표 계산 라이브러리)

#### 테스트 데이터
```yaml
data_sources:
  - provider: "yfinance"        # 무료, 일봉/주봉
  - provider: "ccxt"            # 암호화폐 거래소 데이터 (무료)
  - provider: "alpha_vantage"   # 주식 (무료 API, 일일 한도 있음)

test_assets:                    # 다양한 시장에서 테스트
  stocks: ["SPY", "QQQ", "AAPL", "TSLA"]
  crypto: ["BTC/USDT", "ETH/USDT"]
  forex: ["EUR/USD"]            # (선택사항)

test_periods:
  - name: "bull_market"
    range: "2020-04-01 ~ 2021-11-01"
  - name: "bear_market"
    range: "2022-01-01 ~ 2022-12-31"
  - name: "sideways"
    range: "2023-06-01 ~ 2024-02-01"
  - name: "full_cycle"
    range: "2020-01-01 ~ 2025-01-01"

timeframes: ["1d"]              # 일봉 기준 (분봉은 데이터 확보 어려움)
```

#### 성과 측정 지표
```yaml
metrics:
  returns:
    - total_return_pct           # 총 수익률
    - annual_return_pct          # 연환산 수익률
    - benchmark_excess_return    # 벤치마크(BUY&HOLD) 대비 초과수익률
  risk:
    - max_drawdown_pct           # 최대 낙폭
    - sharpe_ratio               # 샤프 비율 (무위험이자율 = 0.04)
    - sortino_ratio              # 소르티노 비율
    - calmar_ratio               # 칼마 비율
  trading:
    - total_trades               # 총 거래 횟수
    - win_rate_pct               # 승률
    - profit_factor              # 이익비율 (총이익/총손실)
    - avg_trade_return_pct       # 평균 거래 수익률
    - avg_holding_period_days    # 평균 보유 기간
  robustness:
    - consistency_score          # 구간별 수익률 표준편차 (낮을수록 안정적)
    - market_regime_adaptability # 상승/하락/횡보 각 구간에서의 성과
```

#### 백테스팅 파이프라인
```
Phase 1: Quick Scan (빠른 스캔)
  - vectorbt로 모든 전략을 간단히 테스트 (SPY 일봉, full_cycle)
  - 총 수익률 + 샤프비율 기준 상위 20% 선별
  - 예상 소요: 수천 개 전략 → 수 분

Phase 2: Detailed Test (상세 테스트)
  - 상위 전략들에 대해 전체 자산 × 전체 기간 테스트
  - 모든 성과 지표 계산
  - 예상 소요: 수백 개 전략 → 수십 분

Phase 3: Parameter Optimization (파라미터 최적화)
  - 최상위 전략 Top-30에 대해 파라미터 그리드 서치
  - 과적합(Overfitting) 방지: Walk-Forward Analysis 또는 K-Fold 시계열 교차검증
  - 예상 소요: 30개 전략 → 수 시간

Phase 4: Final Ranking (최종 랭킹)
  - 종합 점수 = 0.3×샤프 + 0.2×초과수익 + 0.2×승률 + 0.15×일관성 + 0.15×(1-MDD)
  - Top-10 전략 상세 리포트 생성
```

#### 과적합 방지 메커니즘
- **In-Sample / Out-of-Sample 분리**: 데이터를 70/30으로 나눠 최적화는 IS에서, 검증은 OOS에서
- **Walk-Forward Analysis**: 롤링 윈도우로 최적화 → 검증 반복
- **최소 거래 횟수 필터**: 총 거래 30회 미만인 전략은 통계적 유의성 부족으로 제외
- **파라미터 안정성 검사**: 파라미터를 ±20% 변경해도 성과가 크게 안 바뀌는지 확인

---

## 🔧 기술 스택

```yaml
language: Python 3.11+

core_libraries:
  data:
    - yfinance                   # 주식/ETF 가격 데이터
    - ccxt                       # 암호화폐 거래소 데이터
    - pandas                     # 데이터 처리
  indicators:
    - pandas-ta                  # 기술적 지표 계산 (130+ 내장 지표)
    - ta-lib                     # (선택) C 기반 고속 지표 계산
  backtesting:
    - vectorbt                   # 벡터화 백테스팅 (대규모 병렬 처리)
    - backtrader                 # (보조) 이벤트 기반 백테스팅
  web_scraping:
    - playwright                 # 브라우저 자동화 (TradingView 크롤링)
    - beautifulsoup4             # HTML 파싱
    - httpx                      # 비동기 HTTP 클라이언트
  llm:
    - anthropic                  # Claude API (Pine Script 분석)
  visualization:
    - plotly                     # 인터랙티브 차트
    - matplotlib                 # 정적 차트
  storage:
    - sqlite3                    # 로컬 DB (내장)
    - json                       # 설정/결과 저장

project_structure:
  trading-strategy-pipeline/
  ├── config/
  │   ├── settings.yaml          # 전역 설정 (API 키, 경로 등)
  │   ├── filter_rules.yaml      # 필터링 규칙
  │   └── backtest_config.yaml   # 백테스팅 설정
  ├── src/
  │   ├── collector/
  │   │   ├── tradingview_scraper.py    # TradingView 크롤러
  │   │   ├── github_scraper.py         # GitHub Pine Script 수집
  │   │   └── builtin_indicators.py     # 내장 지표 정의
  │   ├── analyzer/
  │   │   ├── pine_parser.py            # Pine Script 정적 분석기
  │   │   ├── llm_analyzer.py           # LLM 기반 의미 분석
  │   │   └── similarity_detector.py    # 유사 지표 감지
  │   ├── filter/
  │   │   ├── hard_filter.py            # 1차 필터
  │   │   ├── soft_filter.py            # 2차 필터
  │   │   └── role_classifier.py        # 역할 분류
  │   ├── combiner/
  │   │   ├── strategy_template.py      # 전략 템플릿 클래스
  │   │   ├── combination_generator.py  # 조합 생성기
  │   │   └── pine_to_python.py         # Pine → Python 변환기
  │   ├── backtester/
  │   │   ├── data_fetcher.py           # 가격 데이터 수집
  │   │   ├── vectorbt_engine.py        # vectorbt 기반 백테스팅
  │   │   ├── walk_forward.py           # Walk-Forward 분석
  │   │   ├── metrics.py                # 성과 지표 계산
  │   │   └── optimizer.py              # 파라미터 최적화
  │   ├── reporter/
  │   │   ├── ranking.py                # 최종 랭킹 산출
  │   │   └── report_generator.py       # HTML/PDF 리포트 생성
  │   └── utils/
  │       ├── db.py                     # SQLite 헬퍼
  │       ├── logger.py                 # 로깅
  │       └── rate_limiter.py           # API 호출 제한
  ├── data/
  │   ├── raw_scripts/                  # 수집된 Pine Script 원본
  │   ├── analysis_results/             # 분석 결과
  │   ├── price_data/                   # 캐싱된 가격 데이터
  │   └── backtest_results/             # 백테스팅 결과
  ├── reports/                          # 생성된 리포트
  ├── tests/                            # 단위 테스트
  ├── main.py                           # 파이프라인 오케스트레이터
  ├── requirements.txt
  └── README.md
```

---

## 🗄️ 데이터베이스 스키마

```sql
-- 수집된 지표
CREATE TABLE indicators (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT,
    description TEXT,
    category TEXT,              -- JSON array
    likes INTEGER DEFAULT 0,
    pine_version TEXT,
    source_code TEXT NOT NULL,
    source_url TEXT,
    collected_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 분석 결과
CREATE TABLE analysis_results (
    indicator_id TEXT PRIMARY KEY REFERENCES indicators(id),
    -- 정적 분석
    script_type TEXT,            -- indicator / strategy / library
    inputs TEXT,                 -- JSON: 파라미터 목록
    outputs TEXT,                -- JSON: 출력 목록
    dependencies TEXT,           -- JSON: 사용하는 ta.* 함수들
    has_buy_signal BOOLEAN,
    has_sell_signal BOOLEAN,
    signal_type TEXT,
    lines_of_code INTEGER,
    -- LLM 분석
    indicator_category TEXT,     -- 추세추종/모멘텀/변동성/거래량/패턴/복합
    market_condition TEXT,       -- 추세장/횡보장/변동성확대/전체
    timeframe_fit TEXT,          -- 스캘핑/데이트레이딩/스윙/포지션
    signal_clarity_score INTEGER,        -- 1-10
    combination_potential_score INTEGER,  -- 1-10
    overall_auto_trade_score INTEGER,    -- 1-100
    logic_summary TEXT,
    python_difficulty TEXT,      -- 쉬움/보통/어려움/불가능
    similarity_group TEXT,       -- 유사 지표 그룹 ID
    role TEXT,                   -- primary_signal / confirmation / filter / exit
    analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 필터링 결과
CREATE TABLE filtered_indicators (
    indicator_id TEXT PRIMARY KEY REFERENCES indicators(id),
    passed_hard_filter BOOLEAN,
    passed_soft_filter BOOLEAN,
    assigned_role TEXT,
    priority_score REAL,         -- 조합 시 우선순위
    filtered_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 생성된 전략 조합
CREATE TABLE strategies (
    id TEXT PRIMARY KEY,
    primary_indicator_id TEXT NOT NULL,
    primary_params TEXT,         -- JSON
    confirmation_ids TEXT,       -- JSON array
    confirmation_params TEXT,    -- JSON array
    filter_indicator_id TEXT,
    filter_params TEXT,          -- JSON
    exit_indicator_id TEXT,
    exit_params TEXT,            -- JSON
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 백테스팅 결과
CREATE TABLE backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT REFERENCES strategies(id),
    asset TEXT NOT NULL,          -- SPY, BTC/USDT 등
    timeframe TEXT NOT NULL,      -- 1d, 4h 등
    test_period TEXT NOT NULL,    -- bull_market, bear_market 등
    start_date DATE,
    end_date DATE,
    -- 수익률
    total_return_pct REAL,
    annual_return_pct REAL,
    benchmark_return_pct REAL,
    excess_return_pct REAL,
    -- 리스크
    max_drawdown_pct REAL,
    sharpe_ratio REAL,
    sortino_ratio REAL,
    calmar_ratio REAL,
    -- 매매 통계
    total_trades INTEGER,
    win_rate_pct REAL,
    profit_factor REAL,
    avg_trade_return_pct REAL,
    avg_holding_period_days REAL,
    -- 종합
    composite_score REAL,        -- 가중 종합 점수
    tested_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🚀 실행 흐름 (main.py)

```python
"""
파이프라인 실행 예시 — 각 Stage는 독립적으로도 실행 가능해야 한다.
"""

# Stage 1: 수집
python main.py collect --source tradingview --max-scripts 1000 --categories "momentum,trend,volume"
python main.py collect --source github --query "pine script indicator" --max-repos 200

# Stage 2: 분석
python main.py analyze --batch-size 50 --llm-model claude-sonnet-4-20250514 --max-concurrent 5

# Stage 3: 필터링
python main.py filter --min-score 50 --remove-duplicates --assign-roles

# Stage 4: 조합 생성
python main.py combine --max-strategies 1000 --strategy-size 2-4

# Stage 5: 백테스팅
python main.py backtest --phase quick-scan --asset SPY
python main.py backtest --phase detailed --top-pct 20
python main.py backtest --phase optimize --top-n 30
python main.py backtest --phase rank --output reports/final_ranking.html

# 전체 파이프라인 한 번에 실행
python main.py run-all --config config/settings.yaml
```

---

## ⚠️ 주요 제약 조건 및 고려사항

### 크롤링 관련
- TradingView의 이용약관을 확인하고 준수할 것
- 과도한 크롤링은 IP 차단 위험이 있으므로 보수적으로 접근
- 소스코드가 비공개인 스크립트는 수집 불가 (공개 스크립트만 대상)

### Pine Script → Python 변환 관련
- Pine Script의 모든 기능을 Python으로 1:1 변환하는 것은 불가능
- 핵심 로직만 추출하여 pandas-ta / ta-lib의 해당 함수로 매핑하는 전략 사용
- 변환 불가능한 지표는 건너뛰되, 사유를 기록

### 백테스팅 관련
- **슬리피지**: 거래당 0.1% 가정
- **수수료**: 거래당 0.05% 가정 (왕복 0.1%)
- **시장 충격**: 무시 (소액 거래 가정)
- **데이터 한계**: 무료 데이터 소스는 일봉만 안정적으로 확보 가능
- **생존자 편향**: 상폐된 종목이 데이터에 포함되지 않을 수 있음

### 과적합 관련
- 파라미터를 과도하게 최적화하면 미래 성과가 보장되지 않음
- 반드시 Out-of-Sample 검증 포함
- 전략의 단순함(지표 수가 적을수록)에 가산점 부여

---

## 📊 최종 리포트 형식

### 전략 랭킹 테이블 (상위 10개)
| Rank | Strategy ID | 구성 지표 | 총수익률 | 샤프비율 | MDD | 승률 | 종합점수 |
|------|------------|----------|---------|---------|-----|------|---------|
| 1    | STR_042    | RSI + BB + ADX | 127% | 1.85 | -12% | 58% | 87.3 |
| 2    | STR_187    | MACD + Volume + ATR | 98% | 1.62 | -15% | 55% | 82.1 |

### 개별 전략 상세 리포트
- 전략 구성 설명
- 진입/청산 로직 상세
- 자산별/기간별 성과 비교 차트
- 에쿼티 커브 (Equity Curve)
- 드로다운 차트
- 월별 수익률 히트맵
- 파라미터 민감도 분석 결과

---

## 🔑 시작 전 필요한 것

1. **API 키**:
   - Anthropic Claude API Key (Pine Script 분석용)
   - TradingView 계정 (크롤링용, 무료 계정도 가능)
   - (선택) Alpha Vantage API Key

2. **환경**:
   - Python 3.11+
   - 충분한 디스크 공간 (가격 데이터 캐싱: ~1GB)
   - RAM 8GB 이상 권장 (vectorbt 대규모 연산 시)

3. **예상 비용**:
   - Claude API: 지표 1,000개 분석 시 약 $10~30 (모델에 따라 다름)
   - 데이터: 무료 (yfinance, ccxt)
   - 인프라: 로컬 PC에서 실행 가능

---

## 🎬 코딩 지시사항

위의 아키텍처를 기반으로 전체 파이프라인을 Python 프로젝트로 구현하라.

**우선순위:**
1. 먼저 프로젝트 구조와 DB 스키마를 세팅하라.
2. Stage 5 (Backtester)부터 구현하라 — 내장 지표(RSI, MACD, BB 등)로 먼저 작동을 확인해야 이후 단계에서 생성된 전략을 바로 테스트할 수 있다.
3. Stage 2-3 (Analyzer + Filter)를 구현하라.
4. Stage 4 (Combiner)를 구현하라.
5. Stage 1 (Collector)는 마지막에 — 크롤링은 불안정하므로, 나머지가 작동하는 상태에서 수동 수집한 데이터로도 파이프라인을 돌릴 수 있어야 한다.
6. 마지막으로 main.py 오케스트레이터와 리포터를 완성하라.

**코딩 원칙:**
- 각 Stage는 독립적으로 실행 가능해야 한다 (모듈화).
- 중간 결과는 항상 DB/파일에 저장하여 중단 후 재개가 가능해야 한다.
- 모든 외부 API 호출에는 재시도 로직과 rate limiting을 적용하라.
- 로깅은 충분히 상세하게 (각 단계별 진행률, 소요 시간, 에러).
- 설정은 하드코딩 금지, 모두 config 파일에서 관리.
