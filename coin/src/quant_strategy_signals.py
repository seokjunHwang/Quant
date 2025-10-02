import pandas as pd
import numpy as np
import os
from tqdm import tqdm
import warnings
from datetime import datetime
warnings.filterwarnings('ignore')

class QuantStrategySignals:
    def __init__(self, input_folder, output_folder):
        """
        퀀트 전략 시그널 생성기
        
        Parameters:
        input_folder: 기술지표가 포함된 CSV 파일들 폴더
        output_folder: 전략 시그널이 추가된 CSV 저장 폴더
        """
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.processed_data = {}
        self.failed_symbols = []
        
    def load_crypto_data(self, csv_file):
        """CSV 파일 로드"""
        try:
            df = pd.read_csv(csv_file)
            
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index('Date', inplace=True)
            
            return df.sort_index()
            
        except Exception as e:
            print(f"파일 로드 실패 {csv_file}: {e}")
            return None
    
    def calculate_ma_cross_strategies(self, df):
        """이동평균 교차 전략들 - 메모 기반 수정"""
        try:
            # MA_Cross_3_25 - 메모 1-028번
            if 'MA_3' in df.columns and 'MA_25' in df.columns:
                df['MA_Cross_3_25_Signal'] = 1
                cross_up = (df['MA_3'] > df['MA_25']) & (df['MA_3'].shift(1) <= df['MA_25'].shift(1))
                cross_down = (df['MA_3'] < df['MA_25']) & (df['MA_3'].shift(1) >= df['MA_25'].shift(1))
                df.loc[cross_up, 'MA_Cross_3_25_Signal'] = 2
                df.loc[cross_down, 'MA_Cross_3_25_Signal'] = 0
            
            # MA_Trend_20_60_120 - 메모 1-019번
            if all(col in df.columns for col in ['MA_20', 'MA_60', 'MA_120']):
                uptrend = (df['MA_20'] > df['MA_60']) & (df['MA_60'] > df['MA_120'])
                downtrend = (df['MA_20'] < df['MA_60']) & (df['MA_60'] < df['MA_120'])
                df['MA_Trend_Signal'] = 1
                df.loc[uptrend, 'MA_Trend_Signal'] = 2
                df.loc[downtrend, 'MA_Trend_Signal'] = 0
            
            # EMA_Cross_5_20 - 메모 2-114번
            if 'EMA_5' in df.columns and 'EMA_20' in df.columns:
                df['EMA_Cross_5_20_Signal'] = 1
                cross_up = (df['EMA_5'] > df['EMA_20']) & (df['EMA_5'].shift(1) <= df['EMA_20'].shift(1))
                cross_down = (df['EMA_5'] < df['EMA_20']) & (df['EMA_5'].shift(1) >= df['EMA_20'].shift(1))
                df.loc[cross_up, 'EMA_Cross_5_20_Signal'] = 2
                df.loc[cross_down, 'EMA_Cross_5_20_Signal'] = 0
            
            # EMA_Cross_6_24 - 메모 3-253번 골든크로스
            if 'EMA_6' in df.columns and 'EMA_24' in df.columns:
                df['EMA_Cross_6_24_Signal'] = 1
                cross_up = (df['EMA_6'] > df['EMA_24']) & (df['EMA_6'].shift(1) <= df['EMA_24'].shift(1))
                cross_down = (df['EMA_6'] < df['EMA_24']) & (df['EMA_6'].shift(1) >= df['EMA_24'].shift(1))
                df.loc[cross_up, 'EMA_Cross_6_24_Signal'] = 2
                df.loc[cross_down, 'EMA_Cross_6_24_Signal'] = 0
            
            # 정진 전략 - 메모 1-135번
            if 'MA_2' in df.columns and 'MA_29' in df.columns:
                df['Jungjin_Signal'] = 1
                ma2_2days_ago = df['MA_2'].shift(2)
                ma29_2days_ago = df['MA_29'].shift(2)
                buy_condition = (df['Close'] > ma2_2days_ago) & (df['Close'] > ma29_2days_ago)
                sell_condition = (df['Close'] < ma2_2days_ago) & (df['Close'] < ma29_2days_ago)
                df.loc[buy_condition, 'Jungjin_Signal'] = 2
                df.loc[sell_condition, 'Jungjin_Signal'] = 0
            
            return df
        except Exception as e:
            print(f"이동평균 전략 계산 실패: {e}")
            return df

    def calculate_macd_strategies(self, df):
        """MACD 기반 전략들 - 다양한 매개변수 버전 추가"""
        try:
            # 기본 MACD_Zero_Cross (12,26)
            if 'MACD' in df.columns:
                df['MACD_Zero_Cross_Signal'] = 1
                zero_cross_up = (df['MACD'] > 0) & (df['MACD'].shift(1) <= 0)
                zero_cross_down = (df['MACD'] < 0) & (df['MACD'].shift(1) >= 0)
                df.loc[zero_cross_up, 'MACD_Zero_Cross_Signal'] = 2
                df.loc[zero_cross_down, 'MACD_Zero_Cross_Signal'] = 0
            
            # MACD (10,20) 변형 - 메모 1-58번 전략
            if 'MACD_10_20' in df.columns:
                df['MACD_10_20_Signal'] = 1
                zero_cross_up_10_20 = (df['MACD_10_20'] > 0) & (df['MACD_10_20'].shift(1) <= 0)
                zero_cross_down_10_20 = (df['MACD_10_20'] < 0) & (df['MACD_10_20'].shift(1) >= 0)
                df.loc[zero_cross_up_10_20, 'MACD_10_20_Signal'] = 2
                df.loc[zero_cross_down_10_20, 'MACD_10_20_Signal'] = 0
            
            # MACD (15,26) 변형 - 메모 1-144번 전략
            if 'MACD_15_26' in df.columns:
                df['MACD_15_26_Signal'] = 1
                zero_cross_up_15_26 = (df['MACD_15_26'] > 0) & (df['MACD_15_26'].shift(1) <= 0)
                zero_cross_down_15_26 = (df['MACD_15_26'] < 0) & (df['MACD_15_26'].shift(1) >= 0)
                df.loc[zero_cross_up_15_26, 'MACD_15_26_Signal'] = 2
                df.loc[zero_cross_down_15_26, 'MACD_15_26_Signal'] = 0
            
            # MACD (5,27) 변형 - 메모 3-292번 전략
            if 'MACD_5_27' in df.columns:
                df['MACD_5_27_Signal'] = 1
                zero_cross_up_5_27 = (df['MACD_5_27'] > 0) & (df['MACD_5_27'].shift(1) <= 0)
                zero_cross_down_5_27 = (df['MACD_5_27'] < 0) & (df['MACD_5_27'].shift(1) >= 0)
                df.loc[zero_cross_up_5_27, 'MACD_5_27_Signal'] = 2
                df.loc[zero_cross_down_5_27, 'MACD_5_27_Signal'] = 0
            
            # MACD 시그널 교차
            if 'MACD' in df.columns and 'MACD_Signal' in df.columns:
                df['MACD_Signal_Cross'] = 1
                signal_cross_up = (df['MACD'] > df['MACD_Signal']) & (df['MACD'].shift(1) <= df['MACD_Signal'].shift(1))
                signal_cross_down = (df['MACD'] < df['MACD_Signal']) & (df['MACD'].shift(1) >= df['MACD_Signal'].shift(1))
                df.loc[signal_cross_up, 'MACD_Signal_Cross'] = 2
                df.loc[signal_cross_down, 'MACD_Signal_Cross'] = 0
            
            # Bad Market3 전략 (2-114): EMA + MACD 조합
            if all(col in df.columns for col in ['EMA_5', 'EMA_20', 'MACD', 'MACD_Signal']):
                df['Bad_Market3_Signal'] = 1
                
                ema_cross_up = (df['EMA_5'] > df['EMA_20']) & (df['EMA_5'].shift(1) <= df['EMA_20'].shift(1))
                macd_signal_up = (df['MACD'] > df['MACD_Signal']) & (df['MACD'].shift(1) <= df['MACD_Signal'].shift(1))
                buy_condition = ema_cross_up & macd_signal_up
                
                if 'EMA_10' in df.columns:
                    ema_cross_down = (df['EMA_5'] < df['EMA_10']) & (df['EMA_5'].shift(1) >= df['EMA_10'].shift(1))
                    macd_signal_down = (df['MACD'] < df['MACD_Signal']) & (df['MACD'].shift(1) >= df['MACD_Signal'].shift(1))
                    sell_condition = ema_cross_down & macd_signal_down
                    df.loc[sell_condition, 'Bad_Market3_Signal'] = 0
                
                df.loc[buy_condition, 'Bad_Market3_Signal'] = 2
            
            return df
        except Exception as e:
            print(f"MACD 전략 계산 실패: {e}")
            return df

    def calculate_rsi_strategies(self, df):
        """RSI 기반 전략들 - 다양한 매개변수와 임계값"""
        try:
            # 기본 RSI_Reversal (30/70)
            if 'RSI_14' in df.columns:
                df['RSI_Reversal_Signal'] = 1
                oversold_bounce = (df['RSI_14'] > 30) & (df['RSI_14'].shift(1) <= 30)
                overbought_drop = (df['RSI_14'] < 70) & (df['RSI_14'].shift(1) >= 70)
                df.loc[oversold_bounce, 'RSI_Reversal_Signal'] = 2
                df.loc[overbought_drop, 'RSI_Reversal_Signal'] = 0
            
            # RSI_Extreme (20/80)
            if 'RSI_14' in df.columns:
                df['RSI_Extreme_Signal'] = 1
                extreme_oversold = (df['RSI_14'] > 20) & (df['RSI_14'].shift(1) <= 20)
                extreme_overbought = (df['RSI_14'] < 80) & (df['RSI_14'].shift(1) >= 80)
                df.loc[extreme_oversold, 'RSI_Extreme_Signal'] = 2
                df.loc[extreme_overbought, 'RSI_Extreme_Signal'] = 0
            
            # 리버스 RSI (25/64) - 메모 1-178번
            if 'RSI_14' in df.columns:
                df['RSI_Reverse_Signal'] = 1
                reverse_buy = (df['RSI_14'] > 25) & (df['RSI_14'].shift(1) <= 25)
                reverse_sell = (df['RSI_14'] < 64) & (df['RSI_14'].shift(1) >= 64)
                df.loc[reverse_buy, 'RSI_Reverse_Signal'] = 2
                df.loc[reverse_sell, 'RSI_Reverse_Signal'] = 0
            
            # RSI (20/75) - 메모 3-326번
            if 'RSI_21' in df.columns:
                df['RSI_20_75_Signal'] = 1
                rsi_20_buy = (df['RSI_21'] > 20) & (df['RSI_21'].shift(1) <= 20)
                rsi_75_sell = (df['RSI_21'] < 75) & (df['RSI_21'].shift(1) >= 75)
                df.loc[rsi_20_buy, 'RSI_20_75_Signal'] = 2
                df.loc[rsi_75_sell, 'RSI_20_75_Signal'] = 0
            
            # RSI (22/78) - 메모 3-143번
            if 'RSI_20' in df.columns:
                df['RSI_22_78_Signal'] = 1
                rsi_22_buy = (df['RSI_20'] > 22) & (df['RSI_20'].shift(1) <= 22)
                rsi_78_sell = (df['RSI_20'] < 78) & (df['RSI_20'].shift(1) >= 78)
                df.loc[rsi_22_buy, 'RSI_22_78_Signal'] = 2
                df.loc[rsi_78_sell, 'RSI_22_78_Signal'] = 0
            
            # RSI (30/65) - 메모 4-304번
            if 'RSI_4' in df.columns:
                df['RSI_30_65_Signal'] = 1
                rsi_30_buy = (df['RSI_4'] > 30) & (df['RSI_4'].shift(1) <= 30)
                rsi_65_sell = (df['RSI_4'] < 65) & (df['RSI_4'].shift(1) >= 65)
                df.loc[rsi_30_buy, 'RSI_30_65_Signal'] = 2
                df.loc[rsi_65_sell, 'RSI_30_65_Signal'] = 0
            
            # RSI (12/50) - 메모 9-583번
            if 'RSI_12' in df.columns:
                df['RSI_12_50_Signal'] = 1
                rsi_12_buy = (df['RSI_12'] > 12) & (df['RSI_12'].shift(1) <= 12)
                rsi_50_sell = (df['RSI_12'] < 50) & (df['RSI_12'].shift(1) >= 50)
                df.loc[rsi_12_buy, 'RSI_12_50_Signal'] = 2
                df.loc[rsi_50_sell, 'RSI_12_50_Signal'] = 0
            
            return df
        except Exception as e:
            print(f"RSI 전략 계산 실패: {e}")
            return df

    def calculate_oscillator_strategies(self, df):
        """오실레이터 복합 전략들 - 메모 기반 수정"""
        try:
            # Williams_CCI_Combo - 메모 3-191번 기반
            if 'Williams_R_10' in df.columns and 'CCI_10' in df.columns:
                df['Williams_CCI_Signal'] = 1
                williams_buy = (df['Williams_R_10'] > -96) & (df['Williams_R_10'].shift(1) <= -96)
                cci_buy = (df['CCI_10'] > -137) & (df['CCI_10'].shift(1) <= -137)
                combo_buy = williams_buy & cci_buy
                
                williams_sell = (df['Williams_R_10'] < -32) & (df['Williams_R_10'].shift(1) >= -32)
                cci_sell = (df['CCI_10'] < 63) & (df['CCI_10'].shift(1) >= 63)
                combo_sell = williams_sell & cci_sell
                
                df.loc[combo_buy, 'Williams_CCI_Signal'] = 2
                df.loc[combo_sell, 'Williams_CCI_Signal'] = 0
            
            # CCI 과매도/과매수 - 메모 3-026번
            if 'CCI_17' in df.columns:
                df['CCI_Oversold_Signal'] = 1
                cci_buy = (df['CCI_17'] > -100) & (df['CCI_17'].shift(1) <= -100)
                cci_sell = (df['CCI_17'] < 100) & (df['CCI_17'].shift(1) >= 100)
                df.loc[cci_buy, 'CCI_Oversold_Signal'] = 2
                df.loc[cci_sell, 'CCI_Oversold_Signal'] = 0
            
            # CCI (3) -160/120 - 메모 4-362번
            if 'CCI_3' in df.columns:
                df['CCI_3_Signal'] = 1
                cci_3_buy = (df['CCI_3'] > -160) & (df['CCI_3'].shift(1) <= -160)
                cci_3_sell = (df['CCI_3'] < 120) & (df['CCI_3'].shift(1) >= 120)
                df.loc[cci_3_buy, 'CCI_3_Signal'] = 2
                df.loc[cci_3_sell, 'CCI_3_Signal'] = 0
            
            # Stoch_RSI_Combo - 메모 2-249번 기반
            if all(col in df.columns for col in ['Stoch_K_4', 'Stoch_D_4', 'RSI_5']):
                df['Stoch_RSI_Combo_Signal'] = 1
                stoch_cross_up = (df['Stoch_K_4'] > df['Stoch_D_4']) & (df['Stoch_K_4'].shift(1) <= df['Stoch_D_4'].shift(1))
                rsi_bounce = (df['RSI_5'] > 15) & (df['RSI_5'].shift(1) <= 15)
                buy_condition = stoch_cross_up & rsi_bounce
                
                stoch_cross_down = (df['Stoch_K_4'] < df['Stoch_D_4']) & (df['Stoch_K_4'].shift(1) >= df['Stoch_D_4'].shift(1))
                rsi_drop = (df['RSI_5'] < 65) & (df['RSI_5'].shift(1) >= 65)
                sell_condition = stoch_cross_down & rsi_drop
                
                df.loc[buy_condition, 'Stoch_RSI_Combo_Signal'] = 2
                df.loc[sell_condition, 'Stoch_RSI_Combo_Signal'] = 0
            
            # 스토캐스틱 10/72 - 메모 3-231번
            if 'Stoch_K_3' in df.columns:
                df['Stoch_10_72_Signal'] = 1
                stoch_10_buy = (df['Stoch_K_3'] > 10) & (df['Stoch_K_3'].shift(1) <= 10)
                stoch_72_sell = (df['Stoch_K_3'] < 72) & (df['Stoch_K_3'].shift(1) >= 72)
                df.loc[stoch_10_buy, 'Stoch_10_72_Signal'] = 2
                df.loc[stoch_72_sell, 'Stoch_10_72_Signal'] = 0
            
            # 스토캐스틱 71/31 - 메모 8-432번
            if 'Stoch_K_1' in df.columns:
                df['Stoch_71_31_Signal'] = 1
                stoch_71_buy = (df['Stoch_K_1'] > 71) & (df['Stoch_K_1'].shift(1) <= 71)
                stoch_31_sell = (df['Stoch_K_1'] < 31) & (df['Stoch_K_1'].shift(1) >= 31)
                df.loc[stoch_71_buy, 'Stoch_71_31_Signal'] = 0
                df.loc[stoch_31_sell, 'Stoch_71_31_Signal'] = 2
            
            return df
        except Exception as e:
            print(f"오실레이터 전략 계산 실패: {e}")
            return df

    def calculate_price_pattern_strategies(self, df):
        """가격 패턴 기반 전략들"""
        try:
            if all(col in df.columns for col in ['Open', 'High', 'Low', 'Close']):
                # 기본 캔들스틱 패턴
                bullish_candle = (df['Close'] > df['Open']) & \
                                 (abs(df['Close'] - df['Open']) > 0.01) & \
                                 (abs(df['Close'] - df['Open']) < 0.05)
                bearish_candle = (df['Close'] < df['Open']) & \
                                 (abs(df['Close'] - df['Open']) < 0.05)
                
                df['Candlestick_Signal'] = 1
                df.loc[bullish_candle, 'Candlestick_Signal'] = 2
                df.loc[bearish_candle, 'Candlestick_Signal'] = 0
                
                # 수식3 전략 - 메모 7-334번
                df['Formula3_Signal'] = 1
                formula3_buy = (df['Close'] > df['Open']) & \
                               (abs(df['Close'] - df['Open']) > 0.03) & \
                               (abs(df['Close'] - df['Open']) < 0.5)
                formula3_sell = (df['Close'] < df['Open']) & \
                                (abs(df['Close'] - df['Open']) < 0.5)
                
                df.loc[formula3_buy, 'Formula3_Signal'] = 2
                df.loc[formula3_sell, 'Formula3_Signal'] = 0
                
                # Shadow Analysis
                upper_shadow = np.where(df['Close'] > df['Open'], df['High'] - df['Close'], df['High'] - df['Open'])
                lower_shadow = np.where(df['Close'] > df['Open'], df['Open'] - df['Low'], df['Close'] - df['Low'])
                
                long_lower_shadow = lower_shadow > upper_shadow * 2
                long_upper_shadow = upper_shadow > lower_shadow * 2
                
                df['Shadow_Analysis_Signal'] = 1
                df.loc[long_lower_shadow, 'Shadow_Analysis_Signal'] = 2
                df.loc[long_upper_shadow, 'Shadow_Analysis_Signal'] = 0
            
            return df
        except Exception as e:
            print(f"가격 패턴 전략 계산 실패: {e}")
            return df
    
    def calculate_pivot_strategy(self, df):
        """피봇 지지/저항 전략"""
        try:
            if all(col in df.columns for col in ['High', 'Low', 'Close']):
                df['Pivot'] = (df['High'] + df['Low'] + df['Close']) / 3
                df['Support1'] = 2 * df['Pivot'] - df['High']
                df['Resistance1'] = 2 * df['Pivot'] - df['Low']
                
                support_breakout = (df['Close'] > df['Support1']) & (df['Open'] <= df['Support1'])
                resistance_breakdown = (df['Close'] < df['Resistance1']) & (df['Open'] >= df['Resistance1'])
                
                df['Pivot_Strategy_Signal'] = 1
                df.loc[support_breakout, 'Pivot_Strategy_Signal'] = 2
                df.loc[resistance_breakdown, 'Pivot_Strategy_Signal'] = 0
            
            return df
        except Exception as e:
            print(f"피봇 전략 계산 실패: {e}")
            return df
    
    def calculate_volume_strategies(self, df):
        """거래량 기반 전략들 - MFI 전략 세분화"""
        try:
            # 기본 MFI_Strategy (20/80)
            if 'MFI' in df.columns:
                df['MFI_Strategy_Signal'] = 1
                mfi_oversold = (df['MFI'] > 20) & (df['MFI'].shift(1) <= 20)
                mfi_overbought = (df['MFI'] < 80) & (df['MFI'].shift(1) >= 80)
                df.loc[mfi_oversold, 'MFI_Strategy_Signal'] = 2
                df.loc[mfi_overbought, 'MFI_Strategy_Signal'] = 0
            
            # MFI (25/50) - 메모 3-131번
            if 'MFI_11' in df.columns:
                df['MFI_25_50_Signal'] = 1
                mfi_25_buy = (df['MFI_11'] > 25) & (df['MFI_11'].shift(1) <= 25)
                mfi_50_sell = (df['MFI_11'] < 50) & (df['MFI_11'].shift(1) >= 50)
                df.loc[mfi_25_buy, 'MFI_25_50_Signal'] = 2
                df.loc[mfi_50_sell, 'MFI_25_50_Signal'] = 0
            
            # Money Flow Index 극값 - 메모 4-363번
            if 'MFI_11' in df.columns:
                df['MFI_Extreme_Signal'] = 1
                df.loc[df['MFI_11'] <= 15, 'MFI_Extreme_Signal'] = 2
                df.loc[df['MFI_11'] >= 85, 'MFI_Extreme_Signal'] = 0
            
            # Volume_Breakout
            if 'Volume_Ratio' in df.columns:
                df['Volume_Breakout_Signal'] = 1
                volume_surge = (df['Volume_Ratio'] > 2.0) & (df['Volume_Ratio'].shift(1) <= 2.0)
                volume_dry = (df['Volume_Ratio'] < 0.5) & (df['Volume_Ratio'].shift(1) >= 0.5)
                df.loc[volume_surge, 'Volume_Breakout_Signal'] = 2
                df.loc[volume_dry, 'Volume_Breakout_Signal'] = 0
            
            return df
        except Exception as e:
            print(f"거래량 전략 계산 실패: {e}")
            return df

    def calculate_momentum_strategies(self, df):
        """모멘텀 전략들 - Price ROC 추가"""
        try:
            # 기존 Price_ROC (Return_7d 기반)
            if 'Return_7d' in df.columns:
                df['Momentum_Signal'] = 1
                strong_momentum_up = (df['Return_7d'] > 0.1) & (df['Return_7d'].shift(1) <= 0.1)
                strong_momentum_down = (df['Return_7d'] < -0.1) & (df['Return_7d'].shift(1) >= -0.1)
                df.loc[strong_momentum_up, 'Momentum_Signal'] = 2
                df.loc[strong_momentum_down, 'Momentum_Signal'] = 0
            
            # Price ROC (3) - 메모 10-540번
            if 'Price_ROC_3' in df.columns:
                df['Price_ROC_3_Signal'] = 1
                roc_up = (df['Price_ROC_3'] > 0) & (df['Price_ROC_3'].shift(1) <= 0)
                roc_down = (df['Price_ROC_3'] < 0) & (df['Price_ROC_3'].shift(1) >= 0)
                df.loc[roc_up, 'Price_ROC_3_Signal'] = 2
                df.loc[roc_down, 'Price_ROC_3_Signal'] = 0
            
            # Volatility_Breakout
            if 'ATR_Percent_14' in df.columns:
                high_volatility = df['ATR_Percent_14'] > df['ATR_Percent_14'].rolling(20).quantile(0.8)
                low_volatility = df['ATR_Percent_14'] < df['ATR_Percent_14'].rolling(20).quantile(0.2)
                df['Volatility_Signal'] = 1
                df.loc[high_volatility, 'Volatility_Signal'] = 2
                df.loc[low_volatility, 'Volatility_Signal'] = 0
            
            return df
        except Exception as e:
            print(f"모멘텀 전략 계산 실패: {e}")
            return df
    
    def calculate_composite_signals(self, df):
        """복합 시그널 계산"""
        try:
            # 모든 전략 시그널 컬럼 찾기
            signal_columns = [col for col in df.columns if '_Signal' in col and col.endswith('_Signal')]
            
            if len(signal_columns) > 0:
                df['Composite_Signal_Avg'] = df[signal_columns].mean(axis=1)
                
                buy_signals = (df[signal_columns] == 2).sum(axis=1)
                sell_signals = (df[signal_columns] == 0).sum(axis=1)
                
                df['Buy_Signal_Count'] = buy_signals
                df['Sell_Signal_Count'] = sell_signals
                df['Net_Signal_Score'] = buy_signals - sell_signals
                
                df['Final_Composite_Signal'] = 1  # 기본 HOLD
                df.loc[df['Net_Signal_Score'] >= 2, 'Final_Composite_Signal'] = 2  # 강한 매수
                df.loc[df['Net_Signal_Score'] <= -2, 'Final_Composite_Signal'] = 0  # 강한 매도
            
            return df
        except Exception as e:
            print(f"복합 시그널 계산 실패: {e}")
            return df
    
    def process_single_crypto(self, csv_file):
        """개별 코인 처리"""
        symbol = os.path.basename(csv_file).replace('.csv', '')
        
        try:
            print(f"전략 시그널 생성: {symbol}")
            
            df = self.load_crypto_data(csv_file)
            if df is None or len(df) < 50:
                self.failed_symbols.append(symbol)
                return None
            
            print(f"  - 데이터 기간: {df.index[0]} ~ {df.index[-1]} ({len(df)}일)")
            
            # 각 전략 계산 (반환된 df를 다시 할당)
            df = self.calculate_ma_cross_strategies(df)
            df = self.calculate_macd_strategies(df)
            df = self.calculate_rsi_strategies(df)
            df = self.calculate_oscillator_strategies(df)
            df = self.calculate_price_pattern_strategies(df)
            df = self.calculate_pivot_strategy(df)
            df = self.calculate_volume_strategies(df)
            df = self.calculate_momentum_strategies(df)
            
            # 복합 시그널 계산 (반환된 df를 다시 할당)
            df = self.calculate_composite_signals(df)
            
            # 결과 저장
            self.processed_data[symbol] = df
            
            # 새로 추가된 시그널 컬럼 수 계산
            signal_columns = [col for col in df.columns if '_Signal' in col]
            print(f"  - 생성된 전략 시그널: {len(signal_columns)}개")
            
            return df
            
        except Exception as e:
            print(f"⚠️ {symbol} 처리 실패: {e}")
            self.failed_symbols.append(symbol)
            return None
    
    def process_all_cryptos(self):
        """모든 코인 처리"""
        print("🚀 퀀트 전략 시그널 생성 시작!")
        print(f"📁 입력 폴더: {self.input_folder}")
        print("="*50)
        
        csv_files = [f for f in os.listdir(self.input_folder) if f.endswith('.csv')]
        
        if not csv_files:
            print("❌ CSV 파일을 찾을 수 없습니다!")
            return
        
        print(f"📊 총 {len(csv_files)}개 파일 발견")
        
        for csv_file in tqdm(csv_files, desc="전략 시그널 생성"):
            file_path = os.path.join(self.input_folder, csv_file)
            self.process_single_crypto(file_path)
        
        print("="*50)
        print(f"✅ 성공: {len(self.processed_data)}개")
        print(f"❌ 실패: {len(self.failed_symbols)}개")
    
    def save_strategy_data(self):
        """전략 시그널 데이터 저장"""
        print("💾 전략 시그널 데이터 저장 중...")
        
        os.makedirs(self.output_folder, exist_ok=True)
        os.makedirs(f"{self.output_folder}/with_strategies", exist_ok=True)
        
        saved_count = 0
        
        for symbol, df in tqdm(self.processed_data.items(), desc="저장"):
            try:
                df_to_save = df.copy()
                df_to_save.reset_index(inplace=True)
                
                filename = f"{self.output_folder}/with_strategies/{symbol}.csv"
                df_to_save.to_csv(filename, index=False)
                saved_count += 1
                
            except Exception as e:
                print(f"⚠️ {symbol} 저장 실패: {e}")
        
        # 통합 데이터셋 생성
        if self.processed_data:
            self.create_ml_dataset()
        
        # 요약 저장
        summary = {
            'total_processed': len(self.processed_data),
            'total_failed': len(self.failed_symbols),
            'failed_symbols': self.failed_symbols,
            'processing_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        summary_df = pd.DataFrame([summary])
        summary_df.to_csv(f"{self.output_folder}/strategy_summary.csv", index=False)
        
        print(f"✅ 전략 시그널 데이터 저장 완료!")
        print(f"📁 저장 위치: {self.output_folder}/with_strategies/")
        print(f"✅ 저장 완료: {saved_count}개")
    
    def create_ml_dataset(self):
        """머신러닝용 통합 데이터셋 생성 - 수정 버전"""
        try:
            print("🤖 머신러닝용 데이터셋 생성 중...")
            
            ml_columns = [
                'Open', 'High', 'Low', 'Close', 'Volume',
                'MA_7', 'MA_20', 'MA_50', 'EMA_12', 'EMA_26',
                'RSI_14', 'RSI_7', 'MACD', 'MACD_Signal',
                'BB_Position_20', 'Volatility_30d', 'ATR_Percent_14',
                'Volume_Ratio', 'Williams_R', 'MFI',
                'Return_1d', 'Return_7d', 'Return_30d',
                'MA_Cross_3_25_Signal', 'MA_Trend_Signal', 'EMA_Cross_5_20_Signal',
                'MACD_Zero_Cross_Signal', 'MACD_Signal_Cross',
                'RSI_Reversal_Signal', 'RSI_Extreme_Signal',
                'Williams_CCI_Signal', 'Stoch_RSI_Combo_Signal',
                'Candlestick_Signal', 'Shadow_Analysis_Signal',
                'Pivot_Strategy_Signal', 'MFI_Strategy_Signal',
                'Volume_Breakout_Signal', 'Momentum_Signal',
                'Volatility_Signal', 'Final_Composite_Signal',
                'Buy_Signal_Count', 'Sell_Signal_Count', 'Net_Signal_Score'
            ]
            
            combined_data = []
            
            for symbol, df in self.processed_data.items():
                if not df.empty:
                    available_columns = [col for col in ml_columns if col in df.columns]
                    
                    if len(available_columns) >= 20:
                        temp_df = df[available_columns].copy()
                        temp_df['Symbol'] = symbol
                        temp_df['Date'] = temp_df.index
                        temp_df = temp_df.dropna()
                        
                        if len(temp_df) > 100:
                            combined_data.append(temp_df)
            
            if combined_data:
                combined_df = pd.concat(combined_data, ignore_index=True)
                combined_df = combined_df.sort_values(['Symbol', 'Date'])
                
                combined_df['Future_Close_7d'] = combined_df.groupby('Symbol')['Close'].shift(-7)
                combined_df['Future_Return_7d'] = (combined_df['Future_Close_7d'] / combined_df['Close']) - 1
                
                combined_df['Target_Label'] = 1
                combined_df.loc[combined_df['Future_Return_7d'] > 0.05, 'Target_Label'] = 2
                combined_df.loc[combined_df['Future_Return_7d'] < -0.05, 'Target_Label'] = 0
                
                combined_df = combined_df.dropna(subset=['Future_Return_7d', 'Target_Label'])
                combined_df = combined_df.drop(columns=['Future_Close_7d'])
                
                combined_df.to_csv(f"{self.output_folder}/ml_dataset_with_strategies.csv", index=False)
                print(f"🤖 머신러닝 데이터셋 저장 완료: {len(combined_df)}행, {len(combined_df.columns)}개 특성")
                
                target_dist = combined_df['Target_Label'].value_counts().sort_index()
                print(f"  📊 타겟 분포 - SELL(0): {target_dist.get(0, 0)}, HOLD(1): {target_dist.get(1, 0)}, BUY(2): {target_dist.get(2, 0)}")
                
                if len(combined_df) > 0:
                    sample_idx = len(combined_df) // 2
                    print(f"  🔍 검증 샘플:")
                    print(f"    - 현재가: {combined_df.iloc[sample_idx]['Close']:.2f}")
                    print(f"    - 미래 수익률: {combined_df.iloc[sample_idx]['Future_Return_7d']*100:.2f}%")
                    print(f"    - 타겟 라벨: {combined_df.iloc[sample_idx]['Target_Label']} ({['SELL', 'HOLD', 'BUY'][int(combined_df.iloc[sample_idx]['Target_Label'])]})")
        
        except Exception as e:
            print(f"⚠️ ML 데이터셋 생성 실패: {e}")
            
    def get_strategy_summary(self):
        """전략 요약 정보"""
        if not self.processed_data:
            return "처리된 데이터가 없습니다."
        
        sample_symbol = list(self.processed_data.keys())[0]
        sample_df = self.processed_data[sample_symbol]
        
        strategy_columns = [col for col in sample_df.columns if '_Signal' in col]
        
        summary = f"\n📊 생성된 퀀트 전략 시그널 요약 ({sample_symbol} 기준)\n"
        summary += "="*50 + "\n"
        
        strategy_groups = {
            '이동평균 전략': [col for col in strategy_columns if 'MA_' in col or 'EMA_' in col],
            'MACD 전략': [col for col in strategy_columns if 'MACD' in col],
            'RSI 전략': [col for col in strategy_columns if 'RSI' in col],
            '오실레이터 전략': [col for col in strategy_columns if any(x in col for x in ['Williams', 'CCI', 'Stoch'])],
            '가격패턴 전략': [col for col in strategy_columns if any(x in col for x in ['Candlestick', 'Shadow', 'Pivot', 'Formula'])],
            '거래량 전략': [col for col in strategy_columns if any(x in col for x in ['MFI', 'Volume'])],
            '모멘텀 전략': [col for col in strategy_columns if any(x in col for x in ['Momentum', 'Volatility', 'ROC'])],
            '복합 전략': [col for col in strategy_columns if 'Composite' in col or 'Final' in col]
        }
        
        for group, strategies in strategy_groups.items():
            if strategies:
                summary += f"{group}: {len(strategies)}개\n"
                for strategy in strategies:
                    if strategy in sample_df.columns:
                        signal_dist = sample_df[strategy].value_counts().sort_index()
                        buy_pct = (signal_dist.get(2, 0) / len(sample_df) * 100) if len(sample_df) > 0 else 0
                        sell_pct = (signal_dist.get(0, 0) / len(sample_df) * 100) if len(sample_df) > 0 else 0
                        hold_pct = (signal_dist.get(1, 0) / len(sample_df) * 100) if len(sample_df) > 0 else 0
                        summary += f"  - {strategy}: BUY {buy_pct:.1f}%, HOLD {hold_pct:.1f}%, SELL {sell_pct:.1f}%\n"
                summary += "\n"
        
        summary += f"총 전략 시그널: {len(strategy_columns)}개\n"
        summary += f"처리된 코인 수: {len(self.processed_data)}개\n"
        
        return summary
    
    def run_strategy_analysis(self):
        """전체 전략 분석 프로세스 실행"""
        self.process_all_cryptos()
        
        if self.processed_data:
            self.save_strategy_data()
            print(self.get_strategy_summary())
        else:
            print("❌ 처리된 데이터가 없습니다!")
        
        return self.processed_data