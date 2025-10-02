import pandas as pd
import numpy as np
import os
from tqdm import tqdm
import warnings
from datetime import datetime, timedelta
warnings.filterwarnings('ignore')

class CryptoTechnicalIndicators:
    def __init__(self, input_folder, output_folder, start_date=None, end_date=None):
        """
        기술지표 계산기 초기화
        
        Parameters:
        input_folder: 원본 CSV 파일들이 있는 폴더 경로
        output_folder: 기술지표가 추가된 CSV를 저장할 폴더 경로
        start_date: 계산 시작 날짜 (없으면 전체 기간)
        end_date: 계산 종료 날짜 (없으면 전체 기간)
        """
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.start_date = start_date
        self.end_date = end_date
        self.processed_data = {}
        self.failed_symbols = []
        
    def load_crypto_data(self, symbol_file):
        """개별 코인 CSV 파일 로드"""
        try:
            df = pd.read_csv(symbol_file)
            
            # Date 컬럼을 datetime으로 변환하고 인덱스로 설정
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index('Date', inplace=True)
            else:
                # 첫 번째 컬럼이 날짜일 가능성
                df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0])
                df.set_index(df.columns[0], inplace=True)
            
            # 기간 필터링
            if self.start_date:
                df = df[df.index >= self.start_date]
            if self.end_date:
                df = df[df.index <= self.end_date]
            
            # 필수 컬럼 확인
            required_columns = ['Open', 'High', 'Low', 'Close']
            if not all(col in df.columns for col in required_columns):
                return None
            
            # 데이터 정렬 (날짜순)
            df = df.sort_index()
            
            return df
            
        except Exception as e:
            print(f"⚠️ 파일 로드 실패 {symbol_file}: {e}")
            return None
    
    def calculate_moving_averages(self, df):
        """이동평균 계산 - 전략에 필요한 추가 기간 포함"""
        try:
            # 단순 이동평균 (전략에서 요구하는 모든 기간)
            periods = [2, 3, 4, 5, 6, 7, 8, 10, 13, 16, 20, 25, 29, 50, 60, 100, 120, 200]
            for period in periods:
                if len(df) >= period:
                    df[f'MA_{period}'] = df['Close'].rolling(window=period, min_periods=period).mean()
            
            # 지수이동평균 (전략 필요 기간)
            ema_periods = [3, 4, 5, 6, 7, 10, 12, 20, 24, 26, 50]
            for period in ema_periods:
                if len(df) >= period:
                    df[f'EMA_{period}'] = df['Close'].ewm(span=period, min_periods=period).mean()
            
        except Exception as e:
            print(f"⚠️ 이동평균 계산 실패: {e}")
        
        return df
        
    def calculate_macd_variations(self, df):
        """다양한 MACD 변형 계산"""
        try:
            # 기본 MACD (12,26,9)
            if 'EMA_12' in df.columns and 'EMA_26' in df.columns:
                df['MACD'] = df['EMA_12'] - df['EMA_26']
                df['MACD_Signal'] = df['MACD'].ewm(span=9, min_periods=9).mean()
                df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
            
            # MACD (10,20,9) - 메모 1-58번용
            if len(df) >= 20:
                ema_10 = df['Close'].ewm(span=10, min_periods=10).mean()
                ema_20_macd = df['Close'].ewm(span=20, min_periods=20).mean()
                df['MACD_10_20'] = ema_10 - ema_20_macd
                df['MACD_10_20_Signal'] = df['MACD_10_20'].ewm(span=9, min_periods=9).mean()
            
            # MACD (15,26,9) - 메모 1-144번용
            if len(df) >= 26:
                ema_15 = df['Close'].ewm(span=15, min_periods=15).mean()
                if 'EMA_26' in df.columns:
                    df['MACD_15_26'] = ema_15 - df['EMA_26']
                    df['MACD_15_26_Signal'] = df['MACD_15_26'].ewm(span=9, min_periods=9).mean()
            
            # MACD (5,27,9) - 메모 3-292번용
            if len(df) >= 27:
                ema_5_macd = df['Close'].ewm(span=5, min_periods=5).mean()
                ema_27 = df['Close'].ewm(span=27, min_periods=27).mean()
                df['MACD_5_27'] = ema_5_macd - ema_27
                df['MACD_5_27_Signal'] = df['MACD_5_27'].ewm(span=9, min_periods=9).mean()
                
        except Exception as e:
            print(f"⚠️ MACD 변형 계산 실패: {e}")
        
        return df
    
    def calculate_rsi_variations(self, df):
        """다양한 RSI 기간 계산"""
        try:
            # 전략에서 필요한 모든 RSI 기간
            rsi_periods = [4, 5, 6, 7, 12, 14, 20, 21]
            
            for period in rsi_periods:
                if len(df) >= period + 1:
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=period).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=period).mean()
                    
                    rs = np.where(loss > 0, gain / loss, 0)
                    df[f'RSI_{period}'] = 100 - (100 / (1 + rs))
                    
        except Exception as e:
            print(f"⚠️ RSI 변형 계산 실패: {e}")
        
        return df
    
    def calculate_bollinger_bands(self, df, period=20, std_mult=2):
        """볼린저 밴드 계산"""
        try:
            if len(df) >= period:
                df[f'BB_Middle_{period}'] = df['Close'].rolling(window=period, min_periods=period).mean()
                bb_std = df['Close'].rolling(window=period, min_periods=period).std()
                df[f'BB_Upper_{period}'] = df[f'BB_Middle_{period}'] + (bb_std * std_mult)
                df[f'BB_Lower_{period}'] = df[f'BB_Middle_{period}'] - (bb_std * std_mult)
                df[f'BB_Width_{period}'] = df[f'BB_Upper_{period}'] - df[f'BB_Lower_{period}']
                
                # BB Position (0~1 사이의 값)
                df[f'BB_Position_{period}'] = np.where(
                    df[f'BB_Width_{period}'] > 0,
                    (df['Close'] - df[f'BB_Lower_{period}']) / df[f'BB_Width_{period}'],
                    0.5
                )
        except Exception as e:
            print(f"⚠️ 볼린저 밴드 계산 실패: {e}")
        
        return df
    
    def calculate_returns(self, df):
        """수익률 계산"""
        try:
            # 다양한 기간의 수익률
            periods = [1, 3, 7, 14, 30, 90, 180, 365]
            
            # 일일 수익률
            df['Return_1d'] = df['Close'].pct_change(periods=1)
            
            # 다기간 수익률
            for period in periods[1:]:  # 1일 제외
                if len(df) > period:
                    df[f'Return_{period}d'] = df['Close'] / df['Close'].shift(period) - 1
            
            # 누적 수익률
            df['Cumulative_Return'] = (1 + df['Return_1d'].fillna(0)).cumprod() - 1
            
        except Exception as e:
            print(f"⚠️ 수익률 계산 실패: {e}")
        
        return df
    
    def calculate_volatility(self, df):
        """변동성 계산"""
        try:
            periods = [7, 14, 30, 90]
            
            for period in periods:
                if len(df) >= period and 'Return_1d' in df.columns:
                    df[f'Volatility_{period}d'] = df['Return_1d'].rolling(
                        window=period, min_periods=period
                    ).std() * np.sqrt(365)  # 연간화
                    
        except Exception as e:
            print(f"⚠️ 변동성 계산 실패: {e}")
        
        return df
    
    def calculate_volume_indicators(self, df):
        """거래량 지표 계산"""
        try:
            if 'Volume' in df.columns:
                # 거래량 이동평균
                periods = [7, 20, 50]
                for period in periods:
                    if len(df) >= period:
                        df[f'Volume_MA_{period}'] = df['Volume'].rolling(
                            window=period, min_periods=period
                        ).mean()
                
                # 거래량 비율
                if 'Volume_MA_20' in df.columns:
                    df['Volume_Ratio'] = np.where(
                        df['Volume_MA_20'] > 0,
                        df['Volume'] / df['Volume_MA_20'],
                        1
                    )
                
                # 거래량-가격 트렌드
                df['Volume_Price_Trend'] = df['Volume'] * df['Close']
                
        except Exception as e:
            print(f"⚠️ 거래량 지표 계산 실패: {e}")
        
        return df
    
    def calculate_atr(self, df, period=14):
        """ATR (Average True Range) 계산"""
        try:
            if len(df) >= 2:
                # True Range 계산
                df['True_Range'] = np.maximum(
                    df['High'] - df['Low'],
                    np.maximum(
                        abs(df['High'] - df['Close'].shift(1)),
                        abs(df['Low'] - df['Close'].shift(1))
                    )
                )
                
                if len(df) >= period:
                    df[f'ATR_{period}'] = df['True_Range'].rolling(
                        window=period, min_periods=period
                    ).mean()
                    
                    # ATR 퍼센트
                    df[f'ATR_Percent_{period}'] = np.where(
                        df['Close'] > 0,
                        df[f'ATR_{period}'] / df['Close'] * 100,
                        0
                    )
                    
        except Exception as e:
            print(f"⚠️ ATR 계산 실패: {e}")
        
        return df
    
    def calculate_stochastic_variations(self, df):
        """다양한 스토캐스틱 기간 계산"""
        try:
            # 전략에서 필요한 스토캐스틱 조합들
            stoch_configs = [
                (1, 3),    # 메모 8-432, 10-120번용
                (3, 3),    # 메모 3-231번용
                (4, 2),    # 메모 2-249번용
                (5, 3),    # 메모 7-248번용
                (6, 2),    # 메모 7-369번용
                (14, 3)    # 기본
            ]
            
            for k_period, d_period in stoch_configs:
                if len(df) >= k_period:
                    low_k = df['Low'].rolling(window=k_period, min_periods=k_period).min()
                    high_k = df['High'].rolling(window=k_period, min_periods=k_period).max()
                    range_k = high_k - low_k
                    
                    df[f'Stoch_K_{k_period}'] = np.where(
                        range_k > 0,
                        100 * ((df['Close'] - low_k) / range_k),
                        50
                    )
                    
                    if len(df) >= k_period + d_period - 1:
                        df[f'Stoch_D_{k_period}'] = df[f'Stoch_K_{k_period}'].rolling(
                            window=d_period, min_periods=d_period
                        ).mean()
                        
        except Exception as e:
            print(f"⚠️ 스토캐스틱 변형 계산 실패: {e}")
        
        return df

    def calculate_williams_r_variations(self, df):
        """다양한 Williams %R 기간 계산"""
        try:
            # 전략에서 필요한 Williams %R 기간들
            wr_periods = [1, 8, 10, 14]
            
            for period in wr_periods:
                if len(df) >= period:
                    low_period = df['Low'].rolling(window=period, min_periods=period).min()
                    high_period = df['High'].rolling(window=period, min_periods=period).max()
                    range_period = high_period - low_period
                    
                    df[f'Williams_R_{period}'] = np.where(
                        range_period > 0,
                        -100 * (high_period - df['Close']) / range_period,
                        -50
                    )
            
            # 기본 Williams %R도 유지 (14일 기준)
            if 'Williams_R_14' in df.columns:
                df['Williams_R'] = df['Williams_R_14']
                    
        except Exception as e:
            print(f"⚠️ Williams %R 변형 계산 실패: {e}")
        
        return df

    def calculate_cci_variations(self, df):
        """다양한 CCI 기간 계산"""
        try:
            # 전략에서 필요한 CCI 기간들
            cci_periods = [3, 4, 10, 17, 20]
            
            for period in cci_periods:
                if len(df) >= period:
                    tp = (df['High'] + df['Low'] + df['Close']) / 3
                    cci_ma = tp.rolling(window=period, min_periods=period).mean()
                    cci_mad = tp.rolling(window=period, min_periods=period).apply(
                        lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
                    )
                    
                    df[f'CCI_{period}'] = np.where(
                        cci_mad > 0,
                        (tp - cci_ma) / (0.015 * cci_mad),
                        0
                    )
            
            # 기본 CCI도 유지 (20일 기준)
            if 'CCI_20' in df.columns:
                df['CCI'] = df['CCI_20']
                
        except Exception as e:
            print(f"⚠️ CCI 변형 계산 실패: {e}")
        
        return df

    def calculate_mfi_variations(self, df):
        """다양한 MFI 기간 계산"""
        try:
            if 'Volume' not in df.columns:
                return df
                
            # 전략에서 필요한 MFI 기간들
            mfi_periods = [11, 14]
            
            for period in mfi_periods:
                if len(df) >= period:
                    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
                    money_flow = typical_price * df['Volume']
                    mf_sign = np.where(typical_price > typical_price.shift(1), 1, -1)
                    mf_signed = money_flow * mf_sign
                    
                    mf_pos = mf_signed.where(mf_signed > 0, 0).rolling(period, min_periods=period).sum()
                    mf_neg = -mf_signed.where(mf_signed < 0, 0).rolling(period, min_periods=period).sum()
                    
                    df[f'MFI_{period}'] = np.where(
                        mf_neg > 0,
                        100 - (100 / (1 + mf_pos / mf_neg)),
                        50
                    )
            
            # 기본 MFI도 유지 (14일 기준)
            if 'MFI_14' in df.columns:
                df['MFI'] = df['MFI_14']
                
        except Exception as e:
            print(f"⚠️ MFI 변형 계산 실패: {e}")
        
        return df

    def calculate_price_oscillator(self, df):
        """Price Oscillator 계산 (5차 전략용)"""
        try:
            # 전략에서 필요한 Price Oscillator 조합들
            oscp_configs = [
                (11, 36),  # 메모 5차 전략용
                (18, 19),  # 메모 5차 전략용  
                (19, 20)   # 메모 5차 전략용
            ]
            
            for short, long in oscp_configs:
                if len(df) >= long:
                    short_ma = df['Close'].rolling(window=short, min_periods=short).mean()
                    long_ma = df['Close'].rolling(window=long, min_periods=long).mean()
                    
                    df[f'OSCP_{short}_{long}'] = np.where(
                        long_ma > 0,
                        ((short_ma - long_ma) / long_ma) * 100,
                        0
                    )
                    
        except Exception as e:
            print(f"⚠️ Price Oscillator 계산 실패: {e}")
        
        return df

    def calculate_dmi_adx(self, df):
        """DMI와 ADX 계산"""
        try:
            period = 21  # 메모 1-116번용
            
            if len(df) >= period + 1:
                # True Range 계산
                df['TR'] = np.maximum(
                    df['High'] - df['Low'],
                    np.maximum(
                        abs(df['High'] - df['Close'].shift(1)),
                        abs(df['Low'] - df['Close'].shift(1))
                    )
                )
                
                # Directional Movement 계산
                df['DM_Plus'] = np.where(
                    (df['High'] - df['High'].shift(1)) > (df['Low'].shift(1) - df['Low']),
                    np.maximum(df['High'] - df['High'].shift(1), 0),
                    0
                )
                
                df['DM_Minus'] = np.where(
                    (df['Low'].shift(1) - df['Low']) > (df['High'] - df['High'].shift(1)),
                    np.maximum(df['Low'].shift(1) - df['Low'], 0),
                    0
                )
                
                # Smoothed values
                tr_smooth = df['TR'].rolling(window=period, min_periods=period).mean()
                dm_plus_smooth = df['DM_Plus'].rolling(window=period, min_periods=period).mean()
                dm_minus_smooth = df['DM_Minus'].rolling(window=period, min_periods=period).mean()
                
                # DI+ and DI-
                df[f'DI_Plus_{period}'] = np.where(tr_smooth > 0, 100 * dm_plus_smooth / tr_smooth, 0)
                df[f'DI_Minus_{period}'] = np.where(tr_smooth > 0, 100 * dm_minus_smooth / tr_smooth, 0)
                
                # ADX
                dx = np.where(
                    (df[f'DI_Plus_{period}'] + df[f'DI_Minus_{period}']) > 0,
                    100 * abs(df[f'DI_Plus_{period}'] - df[f'DI_Minus_{period}']) / (df[f'DI_Plus_{period}'] + df[f'DI_Minus_{period}']),
                    0
                )
                df[f'ADX_{period}'] = pd.Series(dx).rolling(window=period, min_periods=period).mean()
                
        except Exception as e:
            print(f"⚠️ DMI/ADX 계산 실패: {e}")
        
        return df

    def calculate_price_roc(self, df):
        """Price Rate of Change 계산"""
        try:
            # 전략에서 필요한 ROC 기간들
            roc_periods = [3]  # 메모 10-540번용
            
            for period in roc_periods:
                if len(df) >= period + 1:
                    df[f'Price_ROC_{period}'] = ((df['Close'] / df['Close'].shift(period)) - 1) * 100
                    
        except Exception as e:
            print(f"⚠️ Price ROC 계산 실패: {e}")
        
        return df

    def calculate_standard_deviation(self, df):
        """표준편차 계산 (5차 전략용)"""
        try:
            periods = [1, 20]  # 전략에서 사용하는 기간들
            
            for period in periods:
                if len(df) >= period:
                    df[f'STD_{period}'] = df['Close'].rolling(window=period, min_periods=period).std()
                    
        except Exception as e:
            print(f"⚠️ 표준편차 계산 실패: {e}")
        
        return df

    def calculate_highest_lowest(self, df):
        """최고가/최저가 계산 (전략용)"""
        try:
            # 전략에서 필요한 기간들
            periods = [3, 7, 8, 10, 11, 16, 17, 28]
            
            for period in periods:
                if len(df) >= period:
                    df[f'Highest_{period}'] = df['Close'].rolling(window=period, min_periods=period).max()
                    df[f'Lowest_{period}'] = df['Close'].rolling(window=period, min_periods=period).min()
                    
        except Exception as e:
            print(f"⚠️ 최고가/최저가 계산 실패: {e}")
        
        return df

    def calculate_advanced_indicators(self, df):
        """고급 지표들 계산 - 통합된 함수"""
        try:
            # 기존 지표들 유지 (기본 Williams %R, CCI, MFI)
            
            # Williams %R (기본 14일)
            if len(df) >= 14:
                low_14 = df['Low'].rolling(window=14, min_periods=14).min()
                high_14 = df['High'].rolling(window=14, min_periods=14).max()
                range_14 = high_14 - low_14
                
                df['Williams_R'] = np.where(
                    range_14 > 0,
                    -100 * (high_14 - df['Close']) / range_14,
                    -50
                )
            
            # CCI (기본 20일)
            if len(df) >= 20:
                tp = (df['High'] + df['Low'] + df['Close']) / 3
                cci_ma = tp.rolling(window=20, min_periods=20).mean()
                cci_mad = tp.rolling(window=20, min_periods=20).apply(
                    lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
                )
                
                df['CCI'] = np.where(
                    cci_mad > 0,
                    (tp - cci_ma) / (0.015 * cci_mad),
                    0
                )
            
            # MFI (기본 14일)
            if len(df) >= 14 and 'Volume' in df.columns:
                typical_price = (df['High'] + df['Low'] + df['Close']) / 3
                money_flow = typical_price * df['Volume']
                mf_sign = np.where(typical_price > typical_price.shift(1), 1, -1)
                mf_signed = money_flow * mf_sign
                
                mf_pos = mf_signed.where(mf_signed > 0, 0).rolling(14, min_periods=14).sum()
                mf_neg = -mf_signed.where(mf_signed < 0, 0).rolling(14, min_periods=14).sum()
                
                df['MFI'] = np.where(
                    mf_neg > 0,
                    100 - (100 / (1 + mf_pos / mf_neg)),
                    50
                )
                
        except Exception as e:
            print(f"⚠️ 고급지표 계산 실패: {e}")
        
        return df
    
    def calculate_price_ratios(self, df):
        """가격 비율 지표 계산"""
        try:
            # 이동평균 대비 가격 비율
            ma_periods = [7, 20, 50, 100, 200]
            for period in ma_periods:
                ma_col = f'MA_{period}'
                if ma_col in df.columns:
                    df[f'Price_vs_MA{period}'] = np.where(
                        df[ma_col] > 0,
                        df['Close'] / df[ma_col] - 1,
                        0
                    )
            
            # 고점/저점 대비 현재가 위치
            periods = [52, 200]  # 52일, 200일
            for period in periods:
                if len(df) >= period:
                    rolling_high = df['High'].rolling(window=period, min_periods=period).max()
                    rolling_low = df['Low'].rolling(window=period, min_periods=period).min()
                    range_hl = rolling_high - rolling_low
                    
                    df[f'HighLow_Position_{period}d'] = np.where(
                        range_hl > 0,
                        (df['Close'] - rolling_low) / range_hl,
                        0.5
                    )
                    
        except Exception as e:
            print(f"⚠️ 가격비율 계산 실패: {e}")
        
        return df
    
    def process_single_crypto(self, csv_file):
            """개별 코인 파일 처리 - 향상된 버전"""
            symbol = os.path.basename(csv_file).replace('.csv', '')
            
            try:
                print(f"📊 {symbol} 처리 중...")
                
                # 1. 데이터 로드
                df = self.load_crypto_data(csv_file)
                if df is None or len(df) < 30:  # 최소 데이터 요구량 증가
                    self.failed_symbols.append(symbol)
                    return None
                
                print(f"   - 데이터 기간: {df.index[0]} ~ {df.index[-1]} ({len(df)}일)")
                
                # 2. 기본 기술지표 계산
                df = self.calculate_moving_averages(df)
                df = self.calculate_macd_variations(df)  # 수정된 함수
                df = self.calculate_rsi_variations(df)   # 수정된 함수
                df = self.calculate_bollinger_bands(df)
                df = self.calculate_returns(df)
                df = self.calculate_volatility(df)
                df = self.calculate_volume_indicators(df)
                df = self.calculate_atr(df)
                
                # 3. 전략용 추가 지표 계산
                df = self.calculate_stochastic_variations(df)  # 새로 추가
                df = self.calculate_williams_r_variations(df)  # 새로 추가
                df = self.calculate_cci_variations(df)         # 새로 추가
                df = self.calculate_mfi_variations(df)         # 새로 추가
                df = self.calculate_price_oscillator(df)       # 새로 추가
                df = self.calculate_dmi_adx(df)               # 새로 추가
                df = self.calculate_price_roc(df)             # 새로 추가
                df = self.calculate_standard_deviation(df)     # 새로 추가
                df = self.calculate_highest_lowest(df)        # 새로 추가
                df = self.calculate_advanced_indicators(df)
                df = self.calculate_price_ratios(df)
                
                # 4. 무한값, NaN 처리
                df = df.replace([np.inf, -np.inf], np.nan)
                
                # 5. 결과 저장
                self.processed_data[symbol] = df
                
                print(f"   - 최종 컬럼 수: {len(df.columns)}")
                
                return df
                
            except Exception as e:
                print(f"⚠️ {symbol} 처리 실패: {e}")
                self.failed_symbols.append(symbol)
                return None
    
    def process_all_cryptos(self):
        """모든 코인 파일 처리"""
        print("🚀 기술지표 계산 시작!")
        print(f"📁 입력 폴더: {self.input_folder}")
        print(f"📅 기간: {self.start_date or '전체'} ~ {self.end_date or '전체'}")
        print("="*50)
        
        # CSV 파일 목록 가져오기
        csv_files = [f for f in os.listdir(self.input_folder) if f.endswith('.csv')]
        
        if not csv_files:
            print("❌ CSV 파일을 찾을 수 없습니다!")
            return
        
        print(f"📊 총 {len(csv_files)}개 파일 발견")
        
        # 각 파일 처리
        for csv_file in tqdm(csv_files, desc="기술지표 계산"):
            file_path = os.path.join(self.input_folder, csv_file)
            self.process_single_crypto(file_path)
        
        print("="*50)
        print(f"✅ 성공: {len(self.processed_data)}개")
        print(f"❌ 실패: {len(self.failed_symbols)}개")
        if self.failed_symbols:
            print(f"실패 종목: {', '.join(self.failed_symbols[:10])}{'...' if len(self.failed_symbols) > 10 else ''}")
    
    def save_processed_data(self):
        """처리된 데이터 저장"""
        print("💾 기술지표 추가된 데이터 저장 중...")
        
        # 출력 폴더 생성
        os.makedirs(self.output_folder, exist_ok=True)
        os.makedirs(f"{self.output_folder}/with_indicators", exist_ok=True)
        
        saved_count = 0
        
        # 개별 파일 저장
        for symbol, df in tqdm(self.processed_data.items(), desc="저장"):
            try:
                # Date를 첫 번째 컬럼으로 복원
                df_to_save = df.copy()
                df_to_save.reset_index(inplace=True)
                
                filename = f"{self.output_folder}/with_indicators/{symbol}.csv"
                df_to_save.to_csv(filename, index=False)
                saved_count += 1
                
            except Exception as e:
                print(f"⚠️ {symbol} 저장 실패: {e}")
        
        # 통합 데이터셋 생성 (선택적)
        if self.processed_data:
            self.create_combined_dataset()
        
        # 처리 요약 저장
        summary = {
            'total_processed': len(self.processed_data),
            'total_failed': len(self.failed_symbols),
            'failed_symbols': self.failed_symbols,
            'processing_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'period_filter': f"{self.start_date or 'None'} to {self.end_date or 'None'}"
        }
        
        summary_df = pd.DataFrame([summary])
        summary_df.to_csv(f"{self.output_folder}/processing_summary.csv", index=False)
        
        print(f"✅ 기술지표 데이터 저장 완료!")
        print(f"📁 저장 위치: {self.output_folder}/with_indicators/")
        print(f"✅ 저장 완료: {saved_count}개")
    
    def create_combined_dataset(self):
        """통합 데이터셋 생성"""
        try:
            print("📊 통합 데이터셋 생성 중...")
            
            # 주요 컬럼만 선별
            main_columns = [
                'Open', 'High', 'Low', 'Close', 'Volume',
                'Return_1d', 'Return_7d', 'Return_30d',
                'MA_7', 'MA_20', 'MA_50',
                'EMA_12', 'EMA_26',
                'RSI_14', 'RSI_7',
                'MACD', 'MACD_Signal',
                'BB_Position_20',
                'Volatility_30d',
                'ATR_14', 'ATR_Percent_14',
                'Volume_Ratio',
                'Williams_R', 'MFI'
            ]
            
            combined_data = []
            
            for symbol, df in self.processed_data.items():
                if not df.empty:
                    # 사용 가능한 컬럼만 선택
                    available_columns = [col for col in main_columns if col in df.columns]
                    
                    if len(available_columns) >= 10:  # 최소 10개 컬럼은 있어야 함
                        temp_df = df[available_columns].copy()
                        temp_df['Symbol'] = symbol
                        temp_df['Date'] = temp_df.index
                        combined_data.append(temp_df)
            
            if combined_data:
                combined_df = pd.concat(combined_data, ignore_index=True)
                combined_df.to_csv(f"{self.output_folder}/combined_crypto_indicators.csv", index=False)
                print(f"📊 통합 데이터셋 저장 완료: {len(combined_df)}행")
            
        except Exception as e:
            print(f"⚠️ 통합 데이터셋 생성 실패: {e}")
    
    def get_indicator_summary(self):
        """계산된 지표 요약 정보"""
        if not self.processed_data:
            return "처리된 데이터가 없습니다."
        
        sample_symbol = list(self.processed_data.keys())[0]
        sample_df = self.processed_data[sample_symbol]
        
        # 지표별 그룹화
        indicator_groups = {
            '이동평균': [col for col in sample_df.columns if 'MA_' in col or 'EMA_' in col],
            'MACD': [col for col in sample_df.columns if 'MACD' in col],
            'RSI': [col for col in sample_df.columns if 'RSI' in col],
            '스토캐스틱': [col for col in sample_df.columns if 'Stoch' in col],
            'Williams %R': [col for col in sample_df.columns if 'Williams' in col],
            'CCI': [col for col in sample_df.columns if 'CCI' in col],
            'MFI': [col for col in sample_df.columns if 'MFI' in col],
            '수익률': [col for col in sample_df.columns if 'Return' in col],
            '변동성': [col for col in sample_df.columns if 'Volatility' in col or 'ATR' in col or 'BB_' in col],
            '거래량': [col for col in sample_df.columns if 'Volume' in col],
            '기타': [col for col in sample_df.columns if any(x in col for x in ['OSCP', 'DI_', 'ADX', 'Price_ROC', 'STD', 'Highest', 'Lowest'])]
        }
        
        summary = f"\n📊 계산된 기술지표 요약 ({sample_symbol} 기준)\n"
        summary += "="*50 + "\n"
        
        total_indicators = 0
        for group, indicators in indicator_groups.items():
            if indicators:
                summary += f"{group}: {len(indicators)}개\n"
                for indicator in indicators[:5]:  # 처음 5개만 표시
                    summary += f"  - {indicator}\n"
                if len(indicators) > 5:
                    summary += f"  ... 외 {len(indicators)-5}개 더\n"
                summary += "\n"
                total_indicators += len(indicators)
        
        summary += f"총 지표 수: {total_indicators}개\n"
        summary += f"처리된 코인 수: {len(self.processed_data)}개\n"
        
        return summary
    
    def run_technical_analysis(self):
        """전체 기술분석 프로세스 실행"""
        # 1. 모든 코인 처리
        self.process_all_cryptos()
        
        # 2. 결과 저장
        if self.processed_data:
            self.save_processed_data()
            
            # 3. 요약 정보 출력
            print(self.get_indicator_summary())
        else:
            print("❌ 처리된 데이터가 없습니다!")
        
        return self.processed_data