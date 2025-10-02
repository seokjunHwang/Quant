-- MySQL 진입 후 실행
-- 개선된 퀀트 전략 + AI 모델 시그널 테이블
CREATE DATABASE IF NOT EXISTS trading_signals CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE trading_signals;

-- 1. 메인 시그널 테이블
CREATE TABLE IF NOT EXISTS trading_signals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL COMMENT '전략명 (RSI_REVERSAL, XGBOOST_PREDICTOR, etc)',
    symbol VARCHAR(20) NOT NULL COMMENT '심볼 (BTCUSDT, ETHUSDT, etc)',
    timeframe VARCHAR(10) NOT NULL COMMENT '시간대 (1m, 5m, 15m, 1h, 4h, 1d)',
    signal_type ENUM('LONG', 'SHORT', 'HOLD') NOT NULL COMMENT '시그널 타입',
    signal_source ENUM('TRADINGVIEW', 'AI_MODEL', 'BACKTEST') NOT NULL COMMENT '시그널 소스',
    price DECIMAL(15,8) DEFAULT NULL COMMENT '시그널 발생 시점 가격',
    volume DECIMAL(20,8) DEFAULT NULL COMMENT '거래량',
    confidence DECIMAL(5,4) DEFAULT 0.0000 COMMENT '신뢰도 (0.0000-1.0000)',
    prediction_probability DECIMAL(5,4) DEFAULT NULL COMMENT 'AI 모델 예측 확률',
    features_data JSON COMMENT '모델 입력 특성 데이터',
    model_version VARCHAR(50) DEFAULT NULL COMMENT '사용된 모델 버전',
    message TEXT COMMENT '추가 메시지',
    webhook_data JSON COMMENT '원본 웹훅 데이터 (TradingView용)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '생성시간',
    processed BOOLEAN DEFAULT FALSE COMMENT '처리 여부',
    processed_at TIMESTAMP NULL COMMENT '처리 시간',
    
    -- 인덱스
    INDEX idx_strategy_symbol_time (strategy_name, symbol, created_at),
    INDEX idx_signal_source (signal_source),
    INDEX idx_processed (processed),
    INDEX idx_symbol_timeframe (symbol, timeframe),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='통합 트레이딩 시그널 저장 테이블';

-- 2. 전략 설정 테이블 (전략별 파라미터 관리)
CREATE TABLE IF NOT EXISTS strategy_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL UNIQUE,
    strategy_type ENUM('TECHNICAL', 'AI_MODEL', 'HYBRID') NOT NULL,
    description TEXT COMMENT '전략 설명',
    parameters JSON COMMENT '전략 파라미터 (JSON 형태)',
    is_active BOOLEAN DEFAULT TRUE COMMENT '활성화 여부',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_strategy_type (strategy_type),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='전략 설정 관리 테이블';

-- 3. 지원 심볼 목록 테이블 (동적 심볼 관리)
CREATE TABLE IF NOT EXISTS supported_symbols (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    base_asset VARCHAR(10) NOT NULL COMMENT '기초 자산 (BTC, ETH, etc)',
    quote_asset VARCHAR(10) NOT NULL COMMENT '견적 자산 (USDT, BUSD, etc)',
    exchange VARCHAR(20) DEFAULT 'BINANCE' COMMENT '거래소',
    is_active BOOLEAN DEFAULT TRUE COMMENT '활성화 여부',
    min_notional DECIMAL(15,8) DEFAULT NULL COMMENT '최소 거래 금액',
    price_precision INT DEFAULT 8 COMMENT '가격 정밀도',
    qty_precision INT DEFAULT 6 COMMENT '수량 정밀도',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_base_asset (base_asset),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='지원 심볼 관리 테이블';

-- 4. AI 모델 정보 테이블
CREATE TABLE IF NOT EXISTS ai_models (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_type VARCHAR(50) NOT NULL COMMENT '모델 타입 (XGBOOST, LSTM, etc)',
    version VARCHAR(20) NOT NULL,
    file_path VARCHAR(500) COMMENT '모델 파일 경로',
    features JSON COMMENT '입력 특성 목록',
    target_variable VARCHAR(50) COMMENT '예측 대상 변수',
    performance_metrics JSON COMMENT '모델 성능 지표',
    training_date TIMESTAMP COMMENT '학습 완료 일시',
    is_active BOOLEAN DEFAULT TRUE COMMENT '활성 모델 여부',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_model_version (model_name, version),
    INDEX idx_model_type (model_type),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI 모델 정보 관리 테이블';


-- 5. 실행된 거래 내역을 저장하기 위한 테이블
CREATE TABLE IF NOT EXISTS trade_history (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '고유 ID',
    order_id VARCHAR(255) NOT NULL COMMENT '거래소 주문 ID',
    symbol VARCHAR(20) NOT NULL COMMENT '심볼 (e.g., BTCUSDT)',
    side ENUM('LONG', 'SHORT') NOT NULL COMMENT '포지션 방향',
    trade_type ENUM('ENTRY', 'EXIT') NOT NULL COMMENT '거래 종류 (진입/종료)',
    quantity DECIMAL(20, 8) NOT NULL COMMENT '체결 수량',
    price DECIMAL(15, 8) NOT NULL COMMENT '체결 가격',
    -- ▼▼▼ [수정] leverage 컬럼을 여기에 추가합니다 ▼▼▼
    leverage INT COMMENT '레버리지',
    -- ▲▲▲ [수정] 종료 ▲▲▲
    realized_pnl DECIMAL(20, 8) DEFAULT 0.00 COMMENT '실현 손익 (USDT)',
    commission DECIMAL(20, 8) DEFAULT 0.00 COMMENT '수수료 (USDT)',
    trade_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '체결 시간',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '레코드 생성 시간',

    -- 🔥 빠른 조회를 위한 인덱스 강화
    INDEX idx_symbol_time (symbol, trade_time),
    INDEX idx_trade_type (trade_type),
    INDEX idx_order_id (order_id),
    INDEX idx_side (side),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='실제 체결된 모든 거래 내역 저장';


-- 초기 데이터 삽입

-- 전략 설정 예시 데이터
INSERT INTO strategy_configs (strategy_name, strategy_type, description, parameters) VALUES
('RSI_REVERSAL', 'TECHNICAL', 'RSI 역추세 전략', '{"rsi_period": 14, "oversold": 30, "overbought": 70}'),
('MACD_MOMENTUM', 'TECHNICAL', 'MACD 모멘텀 전략', '{"fast": 12, "slow": 26, "signal": 9}'),
('XGBOOST_PREDICTOR', 'AI_MODEL', 'XGBoost 가격 예측 모델', '{"lookback_period": 20, "prediction_horizon": 1}'),
('BOLLINGER_BREAKOUT', 'TECHNICAL', '볼린저 밴드 브레이크아웃', '{"period": 20, "std_dev": 2}');

-- 지원 심볼 예시 데이터
INSERT INTO supported_symbols (symbol, base_asset, quote_asset) VALUES
('BTCUSDT', 'BTC', 'USDT'),
('ETHUSDT', 'ETH', 'USDT'),
('ADAUSDT', 'ADA', 'USDT'),
('DOTUSDT', 'DOT', 'USDT'),
('LINKUSDT', 'LINK', 'USDT'),
('LTCUSDT', 'LTC', 'USDT'),
('BCHUSDT', 'BCH', 'USDT'),
('XLMUSDT', 'XLM', 'USDT'),
('EOSUSDT', 'EOS', 'USDT'),
('TRXUSDT', 'TRX', 'USDT');

-- AI 모델 예시 데이터
INSERT INTO ai_models (model_name, model_type, version, features, target_variable, performance_metrics) VALUES
('XGBOOST_PRICE_PREDICTOR', 'XGBOOST', 'v1.0', 
 '["close", "volume", "rsi", "macd", "bb_upper", "bb_lower", "sma_20", "ema_12", "volatility"]',
 'next_day_direction',
 '{"accuracy": 0.68, "precision": 0.72, "recall": 0.65, "f1_score": 0.68}');

-- 테스트 시그널 데이터
INSERT INTO trading_signals (strategy_name, symbol, timeframe, signal_type, signal_source, price, confidence, message) VALUES
('RSI_REVERSAL', 'BTCUSDT', '1h', 'LONG', 'TRADINGVIEW', 45000.50, 0.8500, 'RSI 과매도 반등 시그널'),
('XGBOOST_PREDICTOR', 'ETHUSDT', '1d', 'SHORT', 'AI_MODEL', 2800.75, 0.7200, 'AI 모델 하락 예측');



-- 테이블 구조 확인 쿼리
SELECT 'trading_signals' as table_name, COUNT(*) as record_count FROM trading_signals
UNION ALL
SELECT 'strategy_configs' as table_name, COUNT(*) as record_count FROM strategy_configs
UNION ALL  
SELECT 'supported_symbols' as table_name, COUNT(*) as record_count FROM supported_symbols
UNION ALL
SELECT 'ai_models' as table_name, COUNT(*) as record_count FROM ai_models;


-- 실제 거래내역 테이블 보기
SELECT * 
FROM trade_history
ORDER BY id DESC
LIMIT 10;

-- 시그널 테이블 보기
SELECT * 
FROM trading_signals
ORDER BY id DESC
LIMIT 10;