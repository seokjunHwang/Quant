# Pine Script 전략 파이프라인 — 아키텍처 설계

## 프로젝트 목표

사용자가 직접 큐레이션한 TradingView Pine Script 지표를 **자동으로 변환 → 검증 → 분석 → 조합 → 백테스팅**하여, 최적의 자동매매 전략 후보군을 도출하는 파이프라인을 구축한다.

---

## 프로젝트 개요

### 배경
- TradingView에는 커뮤니티가 만든 수만 개의 Pine Script 기반 지표/전략이 공개되어 있다.
- 대량 크롤링은 ToS 위반 리스크, IP 차단, 저품질 데이터 문제가 있다.
- 트레이더 본인이 선별한 지표는 이미 1차 품질 필터링이 된 상태이므로, **수동 큐레이션 + 자동 파이프라인** 모델이 더 효율적이다.

### 핵심 원칙
- **수동 입력, 자동 처리**: 사용자가 Pine Script 파일을 넣으면 나머지는 자동
- **변환 검증 필수**: Claude API가 변환한 Python 코드의 정확성을 반드시 확인
- **점진적 라이브러리 축적**: 검증된 지표는 캐싱하여 재사용
- **Pine Script → Python 변환은 필수**: vectorbt 로컬 백테스팅을 위해 Python 시그널 생성이 필요

### 최종 산출물
1. **검증된 지표 라이브러리**: 변환 + 검증 완료된 Python 시그널 함수 모음
2. **조합 전략 목록**: 역할 기반으로 융합된 복합 전략들
3. **백테스팅 결과 리포트**: 전략별 수익률, 샤프비율, MDD 등 성과 지표
4. **최종 랭킹**: 성과 기준 상위 전략 Top-N 리스트 + 점진적 융합 효과 분석

---

## 3가지 실행 모드

### Mode 1: 단일 지표 백테스팅

```bash
python main.py test rsi_divergence.pine --asset BTC/USDT --period 2023-01-01:2024-12-31 --tf 1d
```

하나의 Pine Script 지표를 단독 전략으로 백테스팅한다.

### Mode 2: 다중 지표 융합 + 백테스팅

```bash
python main.py combine --asset BTC/USDT --period 2023-01-01:2024-12-31 --tf 1d
```

`indicators/pine/` 디렉토리의 모든 지표를 역할 분류 → 조합 생성 → 백테스팅 → 랭킹한다.

### Mode 3: 변환 검증

```bash
python main.py verify rsi_divergence.pine --asset BTC/USDT --recent 100
```

변환된 Python 코드의 시그널을 최근 N봉 차트에 시각화하여, TradingView 화면과 비교 검증한다.

---

## 시스템 아키텍처 (6단계 파이프라인)

```
[Stage 1: Input]  →  [Stage 2: Converter]  →  [Stage 3: Verifier]
                                                      ↓
[Stage 6: Backtester]  ←  [Stage 5: Combiner]  ←  [Stage 4: Analyzer]
         ↓
   [Result Report]
```

---

### Stage 1: 입력 관리자 (Input Manager)

#### 목적
사용자가 수동으로 가져온 Pine Script 파일을 관리한다.

#### 입력 방식

##### 1-1. 로컬 파일 (기본)
사용자가 `.pine` 파일을 직접 디렉토리에 넣는다:
```
ai/indicators/
  ├── pine/                    ← Pine Script 원본 (사용자가 여기에 넣음)
  │   ├── rsi_divergence.pine
  │   ├── supertrend.pine
  │   └── volume_profile.pine
  └── converted/               ← 변환 + 검증 완료된 Python (자동 생성)
      ├── rsi_divergence.py
      └── supertrend.py
```

##### 1-2. TradingView URL 단건 Fetch (선택)
```bash
python main.py fetch "https://www.tradingview.com/script/xxxxx/"
```
- 단일 스크립트 페이지에서 소스코드만 추출 (대량 크롤링 아님)
- 공개 소스코드가 있는 스크립트만 가능
- Playwright로 페이지 렌더링 후 소스코드 추출 → `pine/` 디렉토리에 저장

#### 파일 메타데이터
새 Pine Script 파일 감지 시 자동으로 기본 메타데이터를 생성한다:
```json
{
  "script_id": "파일명 기반 자동 생성",
  "title": "파일명 또는 스크립트 내 주석에서 추출",
  "source_file": "pine/rsi_divergence.pine",
  "added_at": "2025-01-15T10:30:00",
  "conversion_status": "pending | converted | verified | failed",
  "converted_file": "converted/rsi_divergence.py"
}
```

#### 기술 요구사항
- 새 파일 감지: 디렉토리 스캔 (실행 시마다 `pine/` 폴더 확인)
- 중복 방지: 파일 해시 기반 deduplication
- 메타데이터 저장: SQLite `indicators` 테이블

---

### Stage 2: 변환기 (Converter)

#### 목적
Pine Script를 Claude API를 사용하여 **의미 기반으로** Python 시그널 함수로 변환한다.

#### 변환 전략
기계적 파싱(정규식/AST)이 아닌, LLM 기반 **시맨틱 변환**을 사용한다:

```
Pine Script의 ta.rsi()  →  pandas_ta의 ta.rsi()
Pine Script의 ta.sma()  →  pandas_ta의 ta.sma()
Pine Script의 ta.crossover(a, b)  →  (a > b) & (a.shift(1) <= b.shift(1))
...
```

#### Claude API 프롬프트 구조
```
다음 Pine Script 지표를 분석하고 Python으로 변환하라.

[요구사항]
1. pandas-ta 라이브러리를 사용하여 동일한 지표를 계산하라.
2. 매수/매도 시그널을 boolean Series로 반환하는 함수를 생성하라.
3. 함수 시그니처: def generate_signals(df: pd.DataFrame, **params) -> pd.DataFrame
   - 입력: OHLCV DataFrame (columns: open, high, low, close, volume)
   - 출력: 원본 + 'signal' 컬럼 추가 (1=매수, -1=매도, 0=홀드)
4. Pine Script의 input() 파라미터는 함수의 keyword argument로 변환하라.
5. 핵심 로직만 변환하고, 시각화(plot) 관련 코드는 무시하라.

[Pine Script]
{source_code}
```

#### 변환 결과물 형식
```python
"""
원본: pine/rsi_divergence.pine
변환일: 2025-01-15
변환 모델: claude-sonnet-4-20250514
검증 상태: pending
"""
import pandas as pd
import pandas_ta as ta

METADATA = {
    "name": "RSI Divergence",
    "category": "momentum",
    "default_params": {"rsi_length": 14, "overbought": 70, "oversold": 30},
    "description": "RSI 다이버전스 기반 진입/청산 시그널"
}

def generate_signals(df: pd.DataFrame, rsi_length=14, overbought=70, oversold=30) -> pd.DataFrame:
    """Pine Script 원본 로직과 동일한 시그널 생성"""
    result = df.copy()
    result['rsi'] = ta.rsi(result['close'], length=rsi_length)

    result['signal'] = 0
    result.loc[result['rsi'] < oversold, 'signal'] = 1    # 매수
    result.loc[result['rsi'] > overbought, 'signal'] = -1  # 매도

    return result
```

#### 캐싱 규칙
- 변환 성공 시 `converted/` 디렉토리에 `.py` 파일로 저장
- 원본 `.pine` 파일의 해시가 변경되지 않으면 재변환하지 않음
- 재변환 강제: `python main.py convert --force rsi_divergence.pine`

#### 기술 요구사항
- Anthropic Claude API (claude-sonnet-4-20250514 권장, 비용 대비 성능)
- 비동기 배치 변환: `asyncio` + API rate limit 준수
- 변환 실패 시 사유 기록 + 재시도 로직 (최대 3회)

---

### Stage 3: 검증기 (Verifier)

#### 목적
변환된 Python 코드가 원본 Pine Script와 동일한 시그널을 생성하는지 확인한다.

#### 검증 방법

##### 3-1. 시각적 검증 (기본)
```bash
python main.py verify rsi_divergence.pine --asset BTC/USDT --recent 100
```

- 변환된 Python 코드로 최근 100봉에 대한 시그널 생성
- 차트에 매수(▲)/매도(▼) 포인트 오버레이
- 사용자가 TradingView 차트와 비교하여 눈으로 검증
- 출력: plotly 인터랙티브 차트 (HTML) 또는 matplotlib 이미지

##### 3-2. 자동 통계 검증 (보조)
- 시그널 빈도 체크: 전체 기간 대비 시그널 발생 비율이 합리적인지 (0.1% 미만이면 경고)
- 연속 시그널 체크: 같은 방향 시그널이 비정상적으로 연속되는지
- NaN 체크: 시그널 컬럼에 결측값이 과도한지

##### 3-3. 승인 프로세스
```bash
python main.py verify rsi_divergence.pine --approve   # 검증 통과 → 상태를 "verified"로 변경
python main.py verify rsi_divergence.pine --reject     # 검증 실패 → 재변환 요청
```

- `--approve`: 해당 지표의 `conversion_status`를 `verified`로 업데이트
- `--reject`: `failed`로 표시, 재변환 시 이전 실패 사유를 프롬프트에 포함

---

### Stage 4: 분석 + 역할 분류기 (Analyzer)

#### 목적
검증 완료된 지표를 분석하고, 전략 조합 시의 역할을 자동 분류한다.

#### 분석 방식
Stage 2에서 변환 시 Claude API가 이미 기본 분석을 수행하므로, 여기서는 **역할 분류에 집중**한다.

#### 역할 분류 체계
```yaml
roles:
  primary_signal:       # 주 매매 신호 (진입 판단)
    특성: 명확한 매수/매도 시그널 생성
    예시: Supertrend, MACD Crossover, Ichimoku Cloud
  confirmation:         # 보조 확인 (진입 확신도 강화)
    특성: 추가 조건으로 거짓 신호 필터링
    예시: RSI, Stochastic, CCI
  market_filter:        # 시장 상태 필터 (매매 허용/금지)
    특성: 현재 시장이 전략에 적합한지 판단
    예시: ADX(추세 강도), Choppiness Index(횡보 감지)
  exit_signal:          # 청산 전용 신호
    특성: 포지션 종료 타이밍 결정
    예시: ATR Trailing Stop, Chandelier Exit, Parabolic SAR
```

#### LLM 분류 프롬프트
```
다음 Python 시그널 함수와 원본 Pine Script를 분석하여 역할을 분류하라.

[분류 항목]
1. 역할: primary_signal / confirmation / market_filter / exit_signal (복수 가능)
2. 지표 유형: 추세추종 / 모멘텀 / 변동성 / 거래량 / 패턴인식 / 복합
3. 시장 조건 적합성: 추세장 / 횡보장 / 전체
4. 타임프레임 적합성: 스캘핑(1-5분) / 데이트레이딩(15분-1시간) / 스윙(4시간-일봉) / 포지션(주봉+)
5. 조합 시 추천 파트너 유형: 이 지표와 보완적인 역할의 지표 유형

[원본 Pine Script]
{pine_source}

[변환된 Python]
{python_source}
```

#### 산출물
각 지표별 프로필:
```json
{
  "script_id": "rsi_divergence",
  "roles": ["confirmation", "exit_signal"],
  "indicator_type": "모멘텀",
  "market_condition": "전체",
  "timeframe_fit": "스윙",
  "recommended_partners": ["추세추종 primary_signal", "변동성 market_filter"]
}
```

---

### Stage 5: 전략 조합기 (Combiner)

#### 목적
검증된 지표들을 역할 기반으로 조합하여 복합 전략을 생성한다.

#### 조합 방식: 시그널 AND/OR 조합
여러 지표의 **시그널을 논리적으로 결합**하는 방식이다. 수식 자체를 섞는 것이 아닌, 각 지표의 독립적인 시그널을 조건으로 결합한다.

```python
class CompositeStrategy:
    primary_signal: Indicator        # 1개 (필수) — 진입 신호
    confirmation: List[Indicator]    # 0~2개 — 확인 신호
    market_filter: Optional[Indicator]  # 0~1개 — 시장 상태 필터
    exit_signal: Optional[Indicator]    # 0~1개 — 청산 신호

    def should_enter_long(self):
        return (
            self.primary_signal.buy_signal()
            and all(c.confirm_long() for c in self.confirmation)
            and (self.market_filter is None or self.market_filter.allow_trading())
        )

    def should_exit_long(self):
        if self.exit_signal:
            return self.exit_signal.exit_long()
        return self.primary_signal.sell_signal()
```

#### 전략 템플릿 (프리셋)
검증된 구조를 기본 제공한다:

```yaml
templates:
  trend_following:       # 추세추종형
    structure: "추세추종 primary + 모멘텀 confirmation + 추세강도 filter"
    example: "Supertrend(진입) + RSI(확인) + ADX(필터)"

  mean_reversion:        # 평균회귀형
    structure: "모멘텀 primary + 변동성 confirmation + 횡보감지 filter"
    example: "RSI Divergence(진입) + BB(확인) + Choppiness(필터)"

  breakout:              # 돌파형
    structure: "패턴인식 primary + 거래량 confirmation + ATR exit"
    example: "Donchian Breakout(진입) + Volume Spike(확인) + ATR Stop(청산)"
```

#### 조합 생성 규칙
```
1. primary_signal 풀에서 1개 선택
2. confirmation 풀에서 0~2개 선택
3. market_filter 풀에서 0~1개 선택
4. exit_signal 풀에서 0~1개 선택

조합 제약 조건:
- 같은 유형의 지표를 primary + confirmation에 동시 사용 금지
  (예: RSI + Stochastic 둘 다 모멘텀이므로 중복)
- 최소 2개, 최대 4개 지표로 구성
- 각 지표의 주요 파라미터에 대해 기본값 + ±1 변형 (3가지)
```

#### 조합 수 제어
수동 큐레이션된 지표 풀은 보통 5~30개 수준이므로, 전수 조합이 충분히 가능하다:
- 지표 10개 기준: 약 200~500개 조합
- 지표 30개 기준: 약 2,000~5,000개 조합 → 우선순위 샘플링 적용

---

### Stage 6: 백테스팅 엔진 (Backtester)

#### 목적
생성된 전략을 과거 데이터로 성과 측정하고 랭킹한다.

#### 필수 입력 파라미터

```yaml
required:
  asset: "BTC/USDT"                         # 테스트 자산
  period: "2023-01-01:2024-12-31"           # 테스트 기간
  timeframe: "1d"                            # 타임프레임

optional:
  initial_capital: 10000                     # 초기 자본금 (기본: $10,000)
  leverage: 1                                # 레버리지 (기본: 1x)
  commission_pct: 0.05                       # 거래 수수료 % (기본: 0.05%, 왕복 0.1%)
  slippage_pct: 0.1                          # 슬리피지 % (기본: 0.1%)
  benchmark: "buy_and_hold"                  # 벤치마크 전략 (기본: 매수 후 보유)
```

#### 데이터 소스
```yaml
data_sources:
  crypto:
    - provider: "ccxt"                       # Binance, Bybit 등 (무료)
    - provider: "binance_api"                # 직접 호출 (v02 백엔드 연동)
  stocks:
    - provider: "yfinance"                   # 무료, 일봉/주봉
  fallback:
    - provider: "alpha_vantage"              # 무료 API (일일 한도 있음)
```

#### 백테스팅 파이프라인

##### Phase 1: Quick Scan (빠른 스캔)
```
- 대상: 생성된 모든 전략 조합
- 방법: vectorbt로 단일 자산, 단일 기간 테스트
- 기준: 총 수익률 + 샤프비율
- 선별: 상위 20%
- 소요: 수백 개 전략 → 수 분
```

##### Phase 2: Detailed Test (상세 테스트)
```
- 대상: Phase 1 통과 전략
- 방법: 복수 시장 구간 테스트 (상승장/하락장/횡보장)
- 기준: 전체 성과 지표 산출
- 소요: 수십 개 전략 → 수십 분
```

##### Phase 3: Incremental Fusion Analysis (점진적 융합 분석)
```
- 대상: Phase 2 상위 전략
- 방법: 지표를 하나씩 추가하면서 성과 변화 측정
- 목적: 각 지표의 실질적 기여도 확인

  예시 출력:
  Step 1: Supertrend만        → 수익률 45%, 샤프 1.2
  Step 2: + RSI 확인 추가      → 수익률 52%, 샤프 1.5  (↑ 개선)
  Step 3: + Volume 필터 추가   → 수익률 48%, 샤프 1.6  (수익↓ 안정성↑)
```

##### Phase 4: Parameter Optimization (파라미터 최적화)
```
- 대상: 최상위 전략 Top-10
- 방법: 주요 파라미터 그리드 서치
- 과적합 방지: Walk-Forward Analysis
- 소요: 10개 전략 → 수 시간
```

##### Phase 5: Final Ranking (최종 랭킹)
```
- 종합 점수 = 0.3×샤프비율 + 0.2×초과수익 + 0.2×승률 + 0.15×일관성 + 0.15×(1-MDD)
- Top-10 전략 상세 리포트 생성
```

#### 성과 측정 지표
```yaml
metrics:
  returns:
    - total_return_pct              # 총 수익률
    - annual_return_pct             # 연환산 수익률
    - benchmark_excess_return       # 벤치마크(BUY&HOLD) 대비 초과수익률
  risk:
    - max_drawdown_pct              # 최대 낙폭
    - sharpe_ratio                  # 샤프 비율 (무위험이자율 = 0.04)
    - sortino_ratio                 # 소르티노 비율
    - calmar_ratio                  # 칼마 비율
  trading:
    - total_trades                  # 총 거래 횟수
    - win_rate_pct                  # 승률
    - profit_factor                 # 이익비율 (총이익/총손실)
    - avg_trade_return_pct          # 평균 거래 수익률
    - avg_holding_period_days       # 평균 보유 기간
  robustness:
    - consistency_score             # 구간별 수익률 표준편차
    - market_regime_adaptability    # 상승/하락/횡보 각 구간 성과
    - fusion_contribution           # 점진적 융합 시 각 지표 기여도
```

#### 과적합 방지 메커니즘
- **In-Sample / Out-of-Sample 분리**: 70/30으로 나눠 최적화는 IS, 검증은 OOS
- **Walk-Forward Analysis**: 롤링 윈도우로 최적화 → 검증 반복
- **최소 거래 횟수 필터**: 30회 미만 전략은 통계적 유의성 부족으로 제외
- **파라미터 안정성 검사**: ±20% 변경해도 성과가 크게 안 바뀌는지 확인
- **단순함 보너스**: 지표 수가 적은 전략에 가산점 부여

---

## 기술 스택

```yaml
language: Python 3.11+

core_libraries:
  data:
    - yfinance                      # 주식/ETF 가격 데이터
    - ccxt                          # 암호화폐 거래소 데이터
    - pandas                        # 데이터 처리
  indicators:
    - pandas-ta                     # 기술적 지표 계산 (130+ 내장 지표)
  backtesting:
    - vectorbt                      # 벡터화 백테스팅 (대규모 병렬 처리)
  web_scraping:
    - playwright                    # (선택) TradingView 단건 소스코드 fetch
  llm:
    - anthropic                     # Claude API (변환 + 분석)
  visualization:
    - plotly                        # 인터랙티브 차트 (검증용)
  storage:
    - sqlite3                       # 로컬 DB

project_structure:
  ai/
  ├── config/
  │   ├── settings.yaml             # 전역 설정 (API 키, 경로 등)
  │   ├── backtest_config.yaml      # 백테스팅 기본 파라미터
  │   └── templates.yaml            # 전략 템플릿 프리셋
  ├── indicators/
  │   ├── pine/                     # 원본 Pine Script (사용자 입력)
  │   └── converted/                # 변환된 Python 모듈 (자동 생성)
  ├── src/
  │   ├── input_manager.py          # Stage 1: 파일 감지 + 메타데이터 관리
  │   ├── converter.py              # Stage 2: Claude API Pine→Python 변환
  │   ├── verifier.py               # Stage 3: 변환 검증 + 시각화
  │   ├── analyzer.py               # Stage 4: 역할 분류 + 지표 프로파일링
  │   ├── combiner.py               # Stage 5: 역할 기반 전략 조합 생성
  │   ├── backtester/
  │   │   ├── engine.py             # vectorbt 기반 백테스팅 엔진
  │   │   ├── data_fetcher.py       # OHLCV 데이터 수집 + 캐싱
  │   │   ├── walk_forward.py       # Walk-Forward 분석
  │   │   ├── metrics.py            # 성과 지표 계산
  │   │   └── optimizer.py          # 파라미터 최적화
  │   ├── reporter/
  │   │   ├── ranking.py            # 최종 랭킹 산출
  │   │   └── report_generator.py   # 리포트 생성 (HTML/차트)
  │   └── utils/
  │       ├── db.py                 # SQLite 헬퍼
  │       ├── logger.py             # 로깅
  │       └── rate_limiter.py       # API 호출 제한
  ├── data/
  │   ├── price_cache/              # 캐싱된 가격 데이터
  │   └── backtest_results/         # 백테스팅 결과
  ├── reports/                      # 생성된 리포트
  ├── pipeline.db                   # SQLite 데이터베이스
  ├── main.py                       # CLI 오케스트레이터
  └── requirements.txt
```

---

## 데이터베이스 스키마

```sql
-- 수집된 지표 (Pine Script 메타데이터)
CREATE TABLE indicators (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_file TEXT NOT NULL,          -- pine/rsi_divergence.pine
    converted_file TEXT,                -- converted/rsi_divergence.py
    source_code_hash TEXT,             -- 파일 변경 감지용 해시
    pine_version TEXT,
    source_url TEXT,                    -- TradingView URL (있는 경우)
    conversion_status TEXT DEFAULT 'pending',  -- pending/converted/verified/failed
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    converted_at DATETIME,
    verified_at DATETIME
);

-- 분석 결과 (역할 분류)
CREATE TABLE analysis_results (
    indicator_id TEXT PRIMARY KEY REFERENCES indicators(id),
    roles TEXT,                         -- JSON array: ["primary_signal", "confirmation"]
    indicator_type TEXT,                -- 추세추종/모멘텀/변동성/거래량/패턴인식/복합
    market_condition TEXT,              -- 추세장/횡보장/전체
    timeframe_fit TEXT,                 -- 스캘핑/데이트레이딩/스윙/포지션
    recommended_partners TEXT,          -- JSON: 추천 조합 유형
    default_params TEXT,                -- JSON: 기본 파라미터
    description TEXT,                   -- 로직 요약
    analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 생성된 전략 조합
CREATE TABLE strategies (
    id TEXT PRIMARY KEY,
    primary_indicator_id TEXT NOT NULL,
    primary_params TEXT,                -- JSON
    confirmation_ids TEXT,              -- JSON array
    confirmation_params TEXT,           -- JSON array
    filter_indicator_id TEXT,
    filter_params TEXT,                 -- JSON
    exit_indicator_id TEXT,
    exit_params TEXT,                   -- JSON
    template_type TEXT,                 -- trend_following/mean_reversion/breakout/custom
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 백테스팅 결과
CREATE TABLE backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT REFERENCES strategies(id),
    asset TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    period_start DATE,
    period_end DATE,
    period_label TEXT,                  -- bull_market/bear_market/sideways/full
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
    composite_score REAL,
    tested_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 점진적 융합 분석 결과
CREATE TABLE fusion_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT REFERENCES strategies(id),
    step_number INTEGER,                -- 1, 2, 3...
    added_indicator_id TEXT,            -- 이 단계에서 추가된 지표
    added_role TEXT,                    -- 추가된 역할
    -- 이 단계에서의 성과
    sharpe_ratio REAL,
    total_return_pct REAL,
    max_drawdown_pct REAL,
    -- 이전 단계 대비 변화
    sharpe_delta REAL,
    return_delta REAL,
    mdd_delta REAL,
    contribution_score REAL,            -- 이 지표의 기여도 점수
    tested_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 실행 흐름 (main.py CLI)

```bash
# === Mode 1: 단일 지표 백테스팅 ===
# Pine Script 변환 → 검증 → 백테스팅 한 번에 실행
python main.py test supertrend.pine --asset BTC/USDT --period 2023-01-01:2024-12-31 --tf 1d

# === Mode 2: 다중 지표 융합 ===
# pine/ 디렉토리의 모든 지표를 조합하여 백테스팅
python main.py combine --asset BTC/USDT --period 2023-01-01:2024-12-31 --tf 1d

# === Mode 3: 변환 검증 ===
python main.py verify supertrend.pine --asset BTC/USDT --recent 100
python main.py verify supertrend.pine --approve
python main.py verify supertrend.pine --reject --reason "RSI 시그널 타이밍이 1봉 밀림"

# === 개별 Stage 실행 ===
python main.py convert                          # 미변환 Pine Script 일괄 변환
python main.py convert supertrend.pine          # 특정 파일만 변환
python main.py convert --force supertrend.pine  # 강제 재변환
python main.py analyze                          # 검증된 지표 역할 분류
python main.py status                           # 전체 지표 현황 조회

# === 설정 파일 기반 실행 ===
python main.py combine --config config/backtest_config.yaml
```

---

## 주요 제약 조건 및 고려사항

### Pine Script → Python 변환 관련
- Pine Script의 모든 기능을 1:1 변환하는 것은 불가능
- 핵심 로직만 추출하여 pandas-ta 함수로 매핑하는 **시맨틱 변환** 전략 사용
- 변환 불가능한 지표는 건너뛰되, 사유를 기록
- **반드시 Stage 3(Verifier)을 통과한 지표만 백테스팅에 사용**

### 백테스팅 관련
- **슬리피지**: 거래당 0.1% 가정
- **수수료**: 거래당 0.05% 가정 (왕복 0.1%)
- **시장 충격**: 무시 (소액 거래 가정)
- **데이터 한계**: 무료 데이터 소스는 일봉만 안정적으로 확보 가능

### 과적합 관련
- 파라미터를 과도하게 최적화하면 미래 성과가 보장되지 않음
- 반드시 Out-of-Sample 검증 포함
- 전략의 단순함(지표 수가 적을수록)에 가산점 부여

### 비용 관련
- Claude API: 지표 1개 변환 + 분석 ≈ $0.01~0.03 (Sonnet 기준)
- 지표 50개 풀 처리 시 약 $1~2
- 데이터: 무료 (yfinance, ccxt)
- 인프라: 로컬 PC에서 실행 가능

---

## 최종 리포트 형식

### 전략 랭킹 테이블 (상위 10개)
| Rank | Strategy ID | 구성 지표 | 총수익률 | 샤프비율 | MDD | 승률 | 종합점수 |
|------|------------|----------|---------|---------|-----|------|---------|
| 1    | STR_042    | Supertrend + RSI + ADX | 127% | 1.85 | -12% | 58% | 87.3 |
| 2    | STR_187    | MACD + Volume + ATR | 98% | 1.62 | -15% | 55% | 82.1 |

### 점진적 융합 분석
| Step | 추가 지표 | 역할 | 샤프 변화 | 수익률 변화 | MDD 변화 | 기여도 |
|------|----------|------|----------|-----------|---------|--------|
| 1    | Supertrend | primary | 1.2 (base) | 45% (base) | -18% (base) | - |
| 2    | + RSI | confirmation | +0.3 | +7% | -2% | 높음 |
| 3    | + ADX | filter | +0.1 | -3% | +4% | 보통 (안정성↑) |

### 개별 전략 상세 리포트
- 전략 구성 설명 + 각 지표의 역할과 기여도
- 진입/청산 로직 상세
- 에쿼티 커브 (Equity Curve)
- 드로다운 차트
- 시장 구간별 성과 비교 (상승/하락/횡보)

---

## 개발 우선순위

1. **Stage 6 (Backtester)**: 내장 지표(RSI, MACD, BB)로 먼저 작동 확인
2. **Stage 2 (Converter)**: Claude API 기반 Pine→Python 변환
3. **Stage 3 (Verifier)**: 변환 검증 시각화
4. **Stage 1 (Input Manager)**: 파일 관리 + 메타데이터
5. **Stage 4 (Analyzer)**: 역할 분류
6. **Stage 5 (Combiner)**: 전략 조합 생성
7. **main.py**: CLI 오케스트레이터 + 리포터
