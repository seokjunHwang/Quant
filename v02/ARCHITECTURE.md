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

### Strategy Pipeline Flow
1. Collector: Pine Scripts from TradingView/GitHub
2. Analyzer: Static parsing + LLM analysis
3. Filter: Hard/Soft filter → role assignment
4. Combiner: Role-based strategy composition
5. Backtester: vectorbt → rank by composite score

## DynamoDB Tables

| Table | PK | SK | Purpose |
|-------|----|----|---------|
| v02_candles | symbol#interval | timestamp | OHLCV cache |
| v02_signals | symbol | signal_date | AI predictions |
| v02_indicators | symbol#interval#indicator | timestamp | Computed indicator cache |
| v02_pine_scripts | script_id | METADATA | Collected Pine Scripts |
| v02_analysis_results | script_id | ANALYSIS | LLM analysis output |
| v02_strategies | strategy_id | CONFIG | Composite strategies |
| v02_backtest_results | strategy_id | asset#period | Performance metrics |
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
6. Strategy pipeline (5 stages)
