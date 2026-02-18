# v02 Architecture Overview

## Tech Stack
- **Backend**: FastAPI (Python) + DynamoDB (AWS)
- **AI**: Python (pandas-ta, vectorbt, XGBoost, Claude API)
- **Frontend**: Next.js 15 (React 19) + TradingView Lightweight Charts

## Directory Structure

```
v02/
├── backend/          # FastAPI REST API + WebSocket server
├── ai/               # AI pipeline + signals + indicator engine
└── frontend/         # Next.js web dashboard
```

## Data Flow

```
[Frontend]  ←→  [Backend API]  ←→  [DynamoDB]
                     ↕
                [AI Module]
                     ↕
              [Binance API]
```

### Live Chart Flow
1. Frontend requests OHLCV → Backend checks DynamoDB cache → Binance fallback
2. Frontend requests indicators → Backend calls AI engine → returns computed series
3. WebSocket streams live price updates (Backend fans out Binance WS)

### AI Signal Flow
1. Scheduler triggers XGBoost prediction daily
2. Preprocessor fetches data + computes 30+ features
3. Model predicts LONG/HOLD/SHORT → writes to DynamoDB
4. Backend broadcasts via WebSocket → Frontend updates

### Strategy Pipeline Flow (Manual Curation + Auto Pipeline)

3 Modes: `test` (single script) / `combine` (multi-indicator fusion) / `verify` (conversion check)

```
[pine/ 폴더에 사용자가 .pine 파일 배치]
    ↓
1. Input Manager: 새 파일 감지 + 메타데이터 등록
2. Converter: Claude API → Pine Script를 Python 시그널 함수로 시맨틱 변환 (캐싱)
3. Verifier: 변환된 시그널을 차트에 시각화 → 사용자 검증 (approve/reject)
4. Analyzer: 검증된 지표의 역할 자동 분류 (primary/confirmation/filter/exit)
5. Combiner: 역할 기반 전략 조합 생성 + 프리셋 템플릿
6. Backtester: vectorbt → Quick Scan → Detailed Test → Fusion Analysis → Ranking
```

Pipeline uses local SQLite (ai/pipeline.db) — separate from DynamoDB.
See `tradingview_strategy_pipeline_prompt.md` for full design.

## DynamoDB Tables

| Table | PK | SK | Purpose |
|-------|----|----|---------|
| v02_candles | symbol#interval | timestamp | OHLCV cache |
| v02_signals | symbol | signal_date | AI predictions |
| v02_indicators | symbol#interval#indicator | timestamp | Computed indicator cache |
| v02_strategies | strategy_id | CONFIG | Pipeline top-ranked strategies (synced from SQLite) |
| v02_backtest_results | strategy_id | asset#period | Pipeline backtest results (synced from SQLite) |
| v02_user_sessions | session_id | SESSION | Encrypted API keys |

## API Endpoints

### REST (prefix: /api/v1)
- `GET /market/klines` — OHLCV data
- `GET /market/ticker` — 24h ticker
- `GET /indicators` — Computed indicator series for chart
- `GET /indicators/catalog` — Available indicator list
- `GET /signals` — AI signal history
- `GET /signals/latest` — Latest per-symbol signals
- `POST /signals/trigger` — Manual AI run
- `GET /strategies` — Pipeline results
- `POST /pipeline/run` — Trigger pipeline stage
- `POST /trading/orders` — Place order (auth required)
- `GET /trading/positions` — Active positions
- `POST /auth/keys` — Store encrypted Binance keys

### WebSocket
- `WS /ws/price/{symbol}` — Live candle stream
- `WS /ws/signals` — Signal updates
- `WS /ws/orders` — Order/position updates (auth)

## Build Priority
1. Backend foundation + DynamoDB tables
2. AI indicator engine (pandas-ta based)
3. Frontend chart with Lightweight Charts
4. AI signal migration (from v01 XGBoost)
5. Trading integration (Binance Futures)
6. Strategy pipeline (6 stages — see pipeline prompt for details)
