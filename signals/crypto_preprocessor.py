"""
암호화폐 데이터 전처리 모듈 - A00_00 재현
모델 예측을 위한 신규 데이터 전처리
"""
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')


class CryptoPreprocessor:
    """암호화폐 실시간 데이터 전처리기"""
    
    def __init__(self):
        self.scaler = StandardScaler()
        
        # 🔥 특수 심볼 매핑 (야후 파이낸스 티커)
        self.yahoo_symbol_mapping = {
            'TAO': 'TAO22974-USD',  # TAO는 특수 티커 사용
            # 필요시 다른 특수 심볼도 여기에 추가
        }
        
    def fetch_latest_data(self, symbol, days=120):
        """
        최신 데이터 수집 (yfinance 기준)
        
        Args:
            symbol: 종목 심볼 (예: 'BTC', 'ETH', 'TAO')
            days: 수집 기간 (기본 120일)
            
        Returns:
            DataFrame: 수집된 원본 데이터
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # 🔥 특수 심볼 매핑 확인
            if symbol in self.yahoo_symbol_mapping:
                yf_symbol = self.yahoo_symbol_mapping[symbol]
                print(f"   🔄 {symbol} -> {yf_symbol} 매핑")
            else:
                # yfinance 형식으로 변환 (BTC -> BTC-USD)
                yf_symbol = f"{symbol}-USD" if not symbol.endswith('-USD') else symbol
            
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(start=start_date, end=end_date)
            
            if df.empty:
                raise ValueError(f"No data retrieved for {symbol} ({yf_symbol})")
            
            df = df.reset_index()
            df['Symbol'] = symbol.replace('-USD', '').replace('22974', '')  # TAO22974 -> TAO
            
            print(f"✅ {symbol}: {len(df)}일 데이터 수집 완료")
            return df
            
        except Exception as e:
            print(f"❌ {symbol} 데이터 수집 실패: {e}")
            return pd.DataFrame()
    
    def calculate_all_features(self, df):
        """모든 기술 지표 계산 (A00_00 방식)"""
        
        # 1. 기본 지표
        df['Close_return'] = df['Close'].pct_change()
        df['Close_log_return'] = np.log(df['Close'] / df['Close'].shift(1))
        df['Volume_normalized'] = (df['Volume'] - df['Volume'].rolling(30).mean()) / df['Volume'].rolling(30).std()
        df['Volume_log_ratio'] = np.log(df['Volume'] / df['Volume'].shift(1))
        
        # 2. Stochastic (Top20 피처 포함)
        stoch_configs = [(1, 3), (3, 3), (4, 3), (5, 3), (6, 3), (14, 3)]
        for k_period, d_period in stoch_configs:
            low_k = df['Low'].rolling(k_period).min()
            high_k = df['High'].rolling(k_period).max()
            range_k = high_k - low_k
            
            df[f'Stoch_K_{k_period}'] = np.where(range_k > 0, 100 * ((df['Close'] - low_k) / range_k), 50)
            df[f'Stoch_D_{k_period}'] = df[f'Stoch_K_{k_period}'].rolling(d_period).mean()
            df[f'Stoch_{k_period}_K_above_D'] = (df[f'Stoch_K_{k_period}'] > df[f'Stoch_D_{k_period}']).astype(int)
            df[f'Stoch_{k_period}_overbought'] = (df[f'Stoch_K_{k_period}'] > 80).astype(int)
            df[f'Stoch_{k_period}_oversold'] = (df[f'Stoch_K_{k_period}'] < 20).astype(int)
        
        # 3. CCI (Top20 피처 포함)
        cci_periods = [3, 4]
        for period in cci_periods:
            tp = (df['High'] + df['Low'] + df['Close']) / 3
            cci_ma = tp.rolling(period).mean()
            cci_mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
            df[f'CCI_{period}'] = np.where(cci_mad > 0, (tp - cci_ma) / (0.015 * cci_mad), 0)
            df[f'CCI_{period}_overbought'] = (df[f'CCI_{period}'] > 100).astype(int)
            df[f'CCI_{period}_oversold'] = (df[f'CCI_{period}'] < -100).astype(int)
        
        # 4. 변동성 (Top20 피처 포함)
        df['Volatility_7d'] = df['Close_return'].rolling(7).std() * np.sqrt(365)
        df['high_volatility_regime'] = (
            df['Volatility_7d'] > df['Volatility_7d'].rolling(30).quantile(0.8)
        ).astype(int)
        
        df['realized_volatility_7'] = df['Close_log_return'].rolling(7).std() * np.sqrt(365)
        df['realized_volatility_30'] = df['Close_log_return'].rolling(30).std() * np.sqrt(365)
        
        # 5. 모멘텀 시그널 (Top20 피처 포함)
        df['Return_7d'] = df['Close'].pct_change(7)
        df['Momentum_Signal'] = 1
        strong_momentum_up = (df['Return_7d'] > 0.1) & (df['Return_7d'].shift(1) <= 0.1)
        strong_momentum_down = (df['Return_7d'] < -0.1) & (df['Return_7d'].shift(1) >= -0.1)
        df.loc[strong_momentum_up, 'Momentum_Signal'] = 2
        df.loc[strong_momentum_down, 'Momentum_Signal'] = 0
        
        df['Price_change_3d'] = df['Close'].pct_change(3)
        volume_ma = df['Volume'].rolling(7).mean()
        df['Formula3_Signal'] = 1
        formula3_up = (df['Price_change_3d'] > 0.05) & (df['Volume'] > volume_ma)
        formula3_down = (df['Price_change_3d'] < -0.05) & (df['Volume'] > volume_ma)
        df.loc[formula3_up, 'Formula3_Signal'] = 2
        df.loc[formula3_down, 'Formula3_Signal'] = 0
        
        # 6. 시간 피처 (Top20 피처 포함)
        df['Date'] = pd.to_datetime(df['Date'])
        df['year'] = df['Date'].dt.year
        df['month'] = df['Date'].dt.month
        df['quarter'] = df['Date'].dt.quarter
        df['day_of_week'] = df['Date'].dt.dayofweek
        df['is_month_start'] = df['Date'].dt.is_month_start.astype(int)
        df['is_month_end'] = df['Date'].dt.is_month_end.astype(int)
        df['is_quarter_start'] = df['Date'].dt.is_quarter_start.astype(int)
        df['is_quarter_end'] = df['Date'].dt.is_quarter_end.astype(int)
        df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
        df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        
        # 7. SMI (Stochastic Momentum Index)
        k_length, d_length, ema_length = 10, 3, 10
        ll = df['Low'].rolling(k_length).min()
        hh = df['High'].rolling(k_length).max()
        diff = hh - ll
        rdiff = df['Close'] - (hh + ll) / 2
        
        avgrel_step1 = rdiff.ewm(span=d_length, adjust=False).mean()
        avgrel = avgrel_step1.ewm(span=d_length, adjust=False).mean()
        avgdiff_step1 = diff.ewm(span=d_length, adjust=False).mean()
        avgdiff = avgdiff_step1.ewm(span=d_length, adjust=False).mean()
        
        df['SMI'] = np.where(avgdiff != 0, (avgrel / (avgdiff / 2)) * 100, 0)
        df['SMI_signal'] = df['SMI'].ewm(span=d_length, adjust=False).mean()
        df['SMI_ema'] = df['SMI'].ewm(span=ema_length, adjust=False).mean()
        df['SMI_overbought_40'] = (df['SMI_signal'] > 40).astype(int)
        df['SMI_oversold_40'] = (df['SMI_signal'] < -40).astype(int)
        df['SMI_overbought_50'] = (df['SMI_signal'] > 50).astype(int)
        df['SMI_oversold_50'] = (df['SMI_signal'] < -50).astype(int)
        df['SMI_normalized'] = np.clip(df['SMI'] / 100, -1, 1)
        
        # 8. RSI 다이버전스
        rsi_periods = [3, 7, 14, 30]
        for period in rsi_periods:
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).rolling(period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
            rs = gain / loss
            df[f'RSI_{period}'] = 100 - (100 / (1 + rs))
        
        for period in [7, 14]:
            price_lower = (df['Close'] < df['Close'].shift(5)) & (df['Close'].shift(5) < df['Close'].shift(10))
            rsi_higher = (df[f'RSI_{period}'] > df[f'RSI_{period}'].shift(5)) & (df[f'RSI_{period}'].shift(5) > df[f'RSI_{period}'].shift(10))
            df[f'RSI_{period}_bullish_divergence'] = (price_lower & rsi_higher).astype(int)
            
            price_higher = (df['Close'] > df['Close'].shift(5)) & (df['Close'].shift(5) > df['Close'].shift(10))
            rsi_lower = (df[f'RSI_{period}'] < df[f'RSI_{period}'].shift(5)) & (df[f'RSI_{period}'].shift(5) < df[f'RSI_{period}'].shift(10))
            df[f'RSI_{period}_bearish_divergence'] = (price_higher & rsi_lower).astype(int)
        
        # NaN 처리
        df = df.fillna(method='ffill').fillna(0)
        
        return df
    
    def select_top20_features(self, df):
        """A00_00 Top20 + SMI + RSI다이버전스 피처만 선택"""
        
        top20_features = [
            'Stoch_14_K_above_D', 'Stoch_6_K_above_D', 'CCI_4_overbought', 'Formula3_Signal',
            'Stoch_1_K_above_D', 'Stoch_4_K_above_D', 'is_quarter_start', 'high_volatility_regime',
            'is_month_end', 'year', 'Stoch_3_K_above_D', 'Stoch_K_3',
            'is_month_start', 'Momentum_Signal', 'day_of_week', 'Volatility_7d',
            'month_sin', 'CCI_3', 'dow_sin', 'Stoch_5_overbought'
        ]
        
        smi_cols = [col for col in df.columns if 'SMI' in col]
        rsi_divergence_cols = [col for col in df.columns if 'divergence' in col]
        available_top20 = [col for col in top20_features if col in df.columns]
        
        selected_cols = available_top20 + smi_cols + rsi_divergence_cols
        
        return df[selected_cols].copy()
    
    def apply_normalization(self, df):
        """B00_00 방식 정규화 (시그널 피처 제외)"""
        
        SIGNAL_FEATURES = [
            'is_month_start', 'is_month_end', 'is_quarter_start', 'is_quarter_end',
            'Formula3_Signal', 'Momentum_Signal', 'high_volatility_regime',
            'Stoch_1_K_above_D', 'Stoch_3_K_above_D', 'Stoch_4_K_above_D', 'Stoch_5_K_above_D',
            'Stoch_6_K_above_D', 'Stoch_14_K_above_D', 'Stoch_1_overbought', 'Stoch_3_overbought',
            'Stoch_4_overbought', 'Stoch_5_overbought', 'Stoch_6_overbought', 'Stoch_14_overbought',
            'Stoch_1_oversold', 'Stoch_3_oversold', 'Stoch_4_oversold', 'Stoch_5_oversold',
            'Stoch_6_oversold', 'Stoch_14_oversold',
            'CCI_3_overbought', 'CCI_3_oversold', 'CCI_4_overbought', 'CCI_4_oversold',
            'SMI_overbought_40', 'SMI_oversold_40', 'SMI_overbought_50', 'SMI_oversold_50',
            'RSI_7_bullish_divergence', 'RSI_7_bearish_divergence', 
            'RSI_14_bullish_divergence', 'RSI_14_bearish_divergence',
            'month_sin', 'month_cos', 'dow_sin', 'dow_cos', 'year', 'day_of_week'
        ]
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        scale_cols = [col for col in numeric_cols if col not in SIGNAL_FEATURES]
        
        if scale_cols:
            df[scale_cols] = self.scaler.fit_transform(df[scale_cols].fillna(0))
        
        return df
    
    def filter_final_features(self, df):
        """최종 피처 필터링 (학습 제외 컬럼 제거)"""
        
        crypto_exclude = [
            'SMI_ema', 'SMI', 'SMI_normalized',
            'realized_volatility_7', 'realized_volatility_30',
            'quarter', 'dow_cos', 'year'
        ]
        
        final_features = [col for col in df.columns if col not in crypto_exclude]
        df_final = df[final_features].copy()
        df_final = df_final.fillna(0).replace([np.inf, -np.inf], 0)
        
        return df_final
    
    def preprocess_for_prediction(self, symbol):
        """
        예측용 전처리 전체 파이프라인
        
        Args:
            symbol: 종목 심볼 (예: 'BTC', 'ETH', 'TAO')
            
        Returns:
            DataFrame: 모델 입력용 전처리된 데이터 (최신 1행)
        """
        print(f"\n{'='*60}")
        print(f"🔄 {symbol} 전처리 시작")
        print(f"{'='*60}")
        
        # 1. 데이터 수집
        df = self.fetch_latest_data(symbol, days=120)
        if df.empty:
            return None
        
        # 2. 피처 생성
        print("🔧 기술 지표 계산 중...")
        df = self.calculate_all_features(df)
        
        # 3. Top20 + SMI + RSI다이버전스 선택
        print("🎯 주요 피처 선택 중...")
        df = self.select_top20_features(df)
        
        # 4. 정규화
        print("📊 정규화 적용 중...")
        df = self.apply_normalization(df)
        
        # 5. 최종 필터링
        print("✂️  최종 피처 필터링 중...")
        df = self.filter_final_features(df)
        
        # 6. 최신 데이터 1행만 반환
        latest_row = df.iloc[[-1]].copy()
        
        print(f"✅ 전처리 완료: {latest_row.shape[1]}개 피처")
        print(f"{'='*60}\n")
        
        return latest_row