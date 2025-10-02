import pandas as pd
import numpy as np
import os
from tqdm import tqdm

def create_divergence_features(df):
    """가격과 지표간 다이버전스 탐지"""
    
    # 가격 모멘텀 (20일)
    price_momentum = df['Close'].pct_change(20)
    
    # RSI 모멘텀 (20일) 
    rsi_momentum = df['RSI'].diff(20)
    
    # MACD 모멘텀
    macd_momentum = df['MACD'].diff(20)
    
    # 다이버전스 점수 (-1~1)
    rsi_divergence = np.where(
        (price_momentum > 0) & (rsi_momentum < 0), -1,  # 약세 다이버전스
        np.where((price_momentum < 0) & (rsi_momentum > 0), 1, 0)  # 강세 다이버전스
    )
    
    macd_divergence = np.where(
        (price_momentum > 0) & (macd_momentum < 0), -1,
        np.where((price_momentum < 0) & (macd_momentum > 0), 1, 0)
    )
    
    return rsi_divergence, macd_divergence

def create_stochastic_features(df):
    """기존 스토캐스틱 지표 개선"""
    
    # 기존 %K, %D 활용
    stoch_k = df['%K']
    stoch_d = df['%D']
    
    # 스토캐스틱 모멘텀
    stoch_momentum = stoch_k - stoch_d
    
    # 스토캐스틱 과매수/과매도 신호
    stoch_overbought = (stoch_k > 80) & (stoch_d > 80)
    stoch_oversold = (stoch_k < 20) & (stoch_d < 20)
    
    # 스토캐스틱 크로스오버
    stoch_crossover = np.where(
        (stoch_k > stoch_d) & (stoch_k.shift(1) <= stoch_d.shift(1)), 1,  # 골든크로스
        np.where((stoch_k < stoch_d) & (stoch_k.shift(1) >= stoch_d.shift(1)), -1, 0)  # 데드크로스
    )
    
    return stoch_momentum, stoch_overbought, stoch_oversold, stoch_crossover

def create_smi_indicator(df, period=14, smooth1=3, smooth2=3):
    """정확한 SMI (Stochastic Momentum Index) 계산"""
    
    # 1. 기본 계산 요소
    high_low_diff = df['High'] - df['Low']
    close_mid_diff = df['Close'] - (df['High'] + df['Low']) / 2
    
    # 2. 기간별 합계
    sum_close_mid = close_mid_diff.rolling(period).sum()
    sum_high_low = high_low_diff.rolling(period).sum()
    
    # 3. 이중 평활화
    smooth1_close_mid = sum_close_mid.ewm(span=smooth1).mean()
    smooth1_high_low = sum_high_low.ewm(span=smooth1).mean()
    
    smooth2_close_mid = smooth1_close_mid.ewm(span=smooth2).mean()
    smooth2_high_low = smooth1_high_low.ewm(span=smooth2).mean()
    
    # 4. SMI 계산 (-100 ~ +100 범위)
    smi = 100 * (smooth2_close_mid / (smooth2_high_low / 2))
    
    # 5. SMI Signal (SMI의 EMA)
    smi_signal = smi.ewm(span=3).mean()
    
    # 6. SMI 오실레이터
    smi_oscillator = smi - smi_signal
    
    return smi, smi_signal, smi_oscillator

def create_momentum_features(df):
    """추가 모멘텀 지표 생성"""
    
    # 가격 가속도 (모멘텀의 변화율)
    price_acceleration = df['Return_1d'].diff(5)
    
    # 거래량 모멘텀
    volume_momentum = df['Volume_Ratio'].rolling(10).mean()
    
    # 변동성 모멘텀 
    volatility_momentum = df['Volatility_14d'].pct_change(10)
    
    # ATR 기반 모멘텀
    atr_momentum = df['ATR'].pct_change(10)
    
    return price_acceleration, volume_momentum, volatility_momentum, atr_momentum

def create_trend_strength(df):
    """트렌드 강도 측정"""
    
    # 이동평균 정렬도 (상승 트렌드면 MA5 > MA20 > MA50)
    ma_alignment = np.where(
        (df['MA_5'] > df['MA_20']) & (df['MA_20'] > df['MA_50']), 1,  # 강한 상승
        np.where((df['MA_5'] < df['MA_20']) & (df['MA_20'] < df['MA_50']), -1, 0)  # 강한 하락
    )
    
    # 볼린저 밴드 압축/확장
    bb_squeeze = df['BB_Width'] / df['BB_Width'].rolling(20).mean()
    
    # 가격 vs 다중 이동평균 점수
    ma_score = (
        (df['Close'] > df['MA_5']).astype(int) +
        (df['Close'] > df['MA_20']).astype(int) + 
        (df['Close'] > df['MA_50']).astype(int) +
        (df['Close'] > df['MA_200']).astype(int)
    ) - 2  # -2~2 범위
    
    return ma_alignment, bb_squeeze, ma_score

