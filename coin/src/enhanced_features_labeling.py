# A00_03_labeling할때 추가한 지표들

import pandas as pd
import numpy as np
import os
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

def safe_column_check(df, columns):
    """안전한 컬럼 존재 확인"""
    if not isinstance(df, pd.DataFrame):
        return False
    return all(col in df.columns for col in columns)

def calculate_technical_score(df):
    """기술적 신호 강도 점수 계산 - 실제 존재하는 컬럼만 사용"""
    
    try:
        # DataFrame 확인
        if not isinstance(df, pd.DataFrame) or df.empty:
            return pd.Series(0.0, index=range(len(df)) if hasattr(df, '__len__') else range(1))
        
        # 실제 존재하는 컬럼들로만 계산
        technical_score = pd.Series(0.0, index=df.index)
        
        # RSI 기반 점수 (존재하면)
        if 'RSI_14' in df.columns:
            rsi_data = pd.to_numeric(df['RSI_14'], errors='coerce').fillna(50)
            rsi_score = np.where(rsi_data < 30, 1, np.where(rsi_data > 70, -1, 0))
            technical_score += 0.2 * rsi_score
        
        # MACD 기반 점수
        if 'MACD' in df.columns and 'MACD_Signal' in df.columns:
            macd_data = pd.to_numeric(df['MACD'], errors='coerce').fillna(0)
            macd_signal_data = pd.to_numeric(df['MACD_Signal'], errors='coerce').fillna(0)
            macd_score = np.where(macd_data > macd_signal_data, 1, -1)
            technical_score += 0.2 * macd_score
        
        # 이동평균 기반 점수
        if safe_column_check(df, ['MA_7', 'MA_20', 'Close']):
            close_data = pd.to_numeric(df['Close'], errors='coerce').fillna(method='ffill')
            ma7_data = pd.to_numeric(df['MA_7'], errors='coerce').fillna(method='ffill')
            ma20_data = pd.to_numeric(df['MA_20'], errors='coerce').fillna(method='ffill')
            
            ma_score = np.where(close_data > ma7_data, 0.5, -0.5)
            ma_score += np.where(ma7_data > ma20_data, 0.5, -0.5)
            technical_score += 0.2 * ma_score
        
        # 볼린저 밴드 위치
        if 'BB_Position_20' in df.columns:
            bb_position = pd.to_numeric(df['BB_Position_20'], errors='coerce').fillna(0.5)
            bb_score = (bb_position - 0.5) * 2  # -1 to 1로 변환
            technical_score += 0.2 * bb_score
        
        # 스토캐스틱
        if 'Stoch_K_14' in df.columns:
            stoch_data = pd.to_numeric(df['Stoch_K_14'], errors='coerce').fillna(50)
            stoch_score = np.where(stoch_data < 20, 1, np.where(stoch_data > 80, -1, 0))
            technical_score += 0.2 * stoch_score
        
        # 점수를 -1 ~ 1 범위로 클리핑
        technical_score = np.clip(technical_score, -1, 1)
        
        return technical_score
    
    except Exception as e:
        print(f"⚠️ calculate_technical_score 오류: {e}")
        return pd.Series(0.0, index=df.index if isinstance(df, pd.DataFrame) else range(1))

def create_enhanced_features(df):
    """추가적인 고급 기술적 지표 생성"""
    
    try:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return df
        
        # 가격 데이터 확인 및 처리
        if 'Close' not in df.columns:
            return df
            
        close_data = pd.to_numeric(df['Close'], errors='coerce').fillna(method='ffill')
        
        # 1. 가격 모멘텀 지표들
        if len(close_data) > 20:
            df['Price_Momentum_5'] = close_data.pct_change(5)
            df['Price_Momentum_10'] = close_data.pct_change(10)
            df['Price_Momentum_20'] = close_data.pct_change(20)
        
        # 2. 볼륨 지표 (있다면)
        if 'Volume' in df.columns:
            volume_data = pd.to_numeric(df['Volume'], errors='coerce').fillna(0)
            if len(volume_data) > 20:
                df['Volume_MA_20'] = volume_data.rolling(20, min_periods=1).mean()
                df['Volume_Ratio'] = volume_data / df['Volume_MA_20']
        
        # 3. 변동성 지표
        if len(close_data) > 20:
            df['Volatility_20'] = close_data.rolling(20, min_periods=1).std()
            df['Volatility_Ratio'] = df['Volatility_20'] / df['Volatility_20'].rolling(60, min_periods=1).mean()
        
        # 4. RSI 다이버전스 (RSI가 있다면)
        if 'RSI_14' in df.columns and len(close_data) > 20:
            rsi_data = pd.to_numeric(df['RSI_14'], errors='coerce').fillna(50)
            price_momentum = close_data.pct_change(20)
            rsi_momentum = rsi_data.diff(20)
            
            # 다이버전스 신호
            df['RSI_Divergence'] = np.where(
                (price_momentum > 0) & (rsi_momentum < 0), -1,  # 약세 다이버전스
                np.where((price_momentum < 0) & (rsi_momentum > 0), 1, 0)  # 강세 다이버전스
            )
        
        # 5. MACD 개선 신호
        if safe_column_check(df, ['MACD', 'MACD_Signal']):
            macd = pd.to_numeric(df['MACD'], errors='coerce').fillna(0)
            macd_signal = pd.to_numeric(df['MACD_Signal'], errors='coerce').fillna(0)
            df['MACD_Histogram'] = macd - macd_signal
            df['MACD_Cross'] = np.where(
                (macd > macd_signal) & (macd.shift(1) <= macd_signal.shift(1)), 1,
                np.where((macd < macd_signal) & (macd.shift(1) >= macd_signal.shift(1)), -1, 0)
            )
        
        # 6. 지지/저항 레벨 계산
        if len(close_data) > 50:
            df['Support_Level'] = close_data.rolling(50, min_periods=1).min()
            df['Resistance_Level'] = close_data.rolling(50, min_periods=1).max()
            df['Price_Position'] = (close_data - df['Support_Level']) / (df['Resistance_Level'] - df['Support_Level'])
            df['Price_Position'] = df['Price_Position'].fillna(0.5).clip(0, 1)
        
        return df
    
    except Exception as e:
        print(f"⚠️ create_enhanced_features 오류: {e}")
        return df

def calculate_enhanced_technical_score(df):
    """향상된 기술적 점수 계산"""
    
    try:
        # 기본 기술적 점수
        base_score = calculate_technical_score(df)
        
        # 추가 점수 요소들
        enhanced_score = base_score.copy()
        
        # RSI 다이버전스 신호 추가
        if 'RSI_Divergence' in df.columns:
            divergence_data = pd.to_numeric(df['RSI_Divergence'], errors='coerce').fillna(0)
            enhanced_score += 0.1 * divergence_data
        
        # MACD 크로스오버 신호 추가
        if 'MACD_Cross' in df.columns:
            cross_data = pd.to_numeric(df['MACD_Cross'], errors='coerce').fillna(0)
            enhanced_score += 0.1 * cross_data
        
        # 가격 포지션 신호 추가
        if 'Price_Position' in df.columns:
            position_data = pd.to_numeric(df['Price_Position'], errors='coerce').fillna(0.5)
            position_score = (position_data - 0.5) * 2  # -1 to 1 범위로 변환
            enhanced_score += 0.1 * position_score
        
        # 볼륨 신호 추가
        if 'Volume_Ratio' in df.columns:
            volume_ratio = pd.to_numeric(df['Volume_Ratio'], errors='coerce').fillna(1)
            volume_score = np.where(volume_ratio > 1.5, 0.2, np.where(volume_ratio < 0.5, -0.2, 0))
            enhanced_score += volume_score
        
        # 변동성 신호 추가
        if 'Volatility_Ratio' in df.columns:
            vol_ratio = pd.to_numeric(df['Volatility_Ratio'], errors='coerce').fillna(1)
            vol_score = np.where(vol_ratio > 2, -0.1, np.where(vol_ratio < 0.5, 0.1, 0))
            enhanced_score += vol_score
        
        # 최종 점수 클리핑
        enhanced_score = np.clip(enhanced_score, -1, 1)
        
        return enhanced_score
    
    except Exception as e:
        print(f"⚠️ calculate_enhanced_technical_score 오류: {e}")
        return calculate_technical_score(df)

def create_composite_score(df):
    """복합 점수 생성 - 올바른 미래 수익률 계산"""
    
    try:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return pd.Series(0.0, index=range(1)), {}
        
        # 미래 수익률 직접 계산
        available_returns = {}
        
        if 'Close' in df.columns:
            close_data = pd.to_numeric(df['Close'], errors='coerce')
            
            # 각 기간별 미래 수익률 계산
            periods = {
                'future_1d': 1,
                'future_3d': 3, 
                'future_7d': 7,
                'future_14d': 14,
                'future_30d': 30,
                'future_90d': 90,
                'future_180d': 180,
                'future_365d': 365
            }
            
            for key, days in periods.items():
                if len(close_data) > days:
                    future_close = close_data.shift(-days)
                    future_return = (future_close / close_data) - 1
                    if not future_return.isna().all():
                        available_returns[key] = future_return
        
        # 가중치 설정
        weights = {
            'future_1d': 0.35,
            'future_3d': 0.25, 
            'future_7d': 0.20,
            'future_14d': 0.10,
            'future_30d': 0.05,
            'future_90d': 0.03,
            'future_180d': 0.02,
            'future_365d': 0.0
        }
        
        # 실제 존재하는 컬럼들의 가중치 정규화
        total_weight = sum(weights.get(key, 0) for key in available_returns.keys())
        if total_weight > 0:
            normalized_weights = {key: weights.get(key, 0)/total_weight for key in available_returns.keys()}
        else:
            normalized_weights = {}
        
        # 수익률 기반 점수 계산
        return_score = pd.Series(0.0, index=df.index)
        
        for key, future_return in available_returns.items():
            if key in normalized_weights and normalized_weights[key] > 0:
                clean_return = future_return.fillna(0)
                return_score += normalized_weights[key] * clean_return
        
        # 최종 복합 점수
        composite_score = np.clip(return_score, -0.25, 0.25) * 10
        
        return composite_score, available_returns
    
    except Exception as e:
        print(f"⚠️ create_composite_score 오류: {e}")
        return pd.Series(0.0, index=df.index if isinstance(df, pd.DataFrame) else range(1)), {}

def score_to_label(composite_score):
    """점수를 3단계 라벨로 변환 (강매도, 홀드, 강매수)"""
    
    try:
        # 유효한 점수만 추출 (NaN 제외)
        valid_scores = composite_score.dropna()
        
        if len(valid_scores) == 0:
            return pd.Series([1] * len(composite_score), index=composite_score.index)
        
        # 백분위수 기준으로 라벨 생성
        labels = pd.Series(1, index=composite_score.index)  # 기본값: 홀드
        
        # 3분할 방식 (더 균형잡힌 분포)
        buy_threshold = np.percentile(valid_scores, 55)   # 상위 45%
        sell_threshold = np.percentile(valid_scores, 45)  # 하위 45%
        
        labels[composite_score >= buy_threshold] = 2  # 강매수
        labels[composite_score <= sell_threshold] = 0  # 강매도
        
        return labels
    
    except Exception as e:
        print(f"⚠️ score_to_label 오류: {e}")
        return pd.Series([1] * len(composite_score), index=composite_score.index)

def debug_data_structure(data, symbol="Unknown"):
    """데이터 구조 디버깅"""
    print(f"🔍 {symbol} 데이터 분석:")
    print(f"   타입: {type(data)}")
    
    if isinstance(data, pd.DataFrame):
        print(f"   DataFrame 크기: {data.shape}")
        print(f"   컬럼들: {list(data.columns)[:10]}...")  # 처음 10개만
        return True
    elif isinstance(data, pd.Series):
        print(f"   Series 길이: {len(data)}")
        print(f"   인덱스 타입: {type(data.index)}")
        return False
    elif isinstance(data, dict):
        print(f"   Dictionary 키들: {list(data.keys())[:10]}...")
        return False
    else:
        print(f"   지원되지 않는 타입")
        return False

def enhance_crypto_data_with_labels(crypto_data, test_symbols=None, save_path="enhanced_crypto_data", debug_mode=False):
    """암호화폐 데이터에 기술적 지표와 라벨 추가 - 완전히 개선된 버전"""
    
    from tqdm import tqdm
    
    # 테스트 심볼 설정
    if test_symbols is None:
        symbols_to_process = list(crypto_data.keys())
    else:
        symbols_to_process = test_symbols
    
    # 저장 경로 생성
    os.makedirs(save_path, exist_ok=True)
    
    enhanced_cryptos = {}
    failed_symbols = []
    
    print(f"처리할 암호화폐 수: {len(symbols_to_process)}")
    print("="*50)
    
    for symbol in tqdm(symbols_to_process, desc="데이터 처리 및 라벨링"):
        try:
            # 데이터 가져오기 및 타입 확인
            raw_data = crypto_data[symbol]
            
            if debug_mode:
                is_dataframe = debug_data_structure(raw_data, symbol)
                if not is_dataframe:
                    failed_symbols.append(f"{symbol}: 잘못된 데이터 타입")
                    continue
            
            # DataFrame이 아닌 경우 건너뛰기
            if not isinstance(raw_data, pd.DataFrame):
                failed_symbols.append(f"{symbol}: DataFrame이 아님 - {type(raw_data)}")
                continue
            
            # 빈 DataFrame 확인
            if raw_data.empty:
                failed_symbols.append(f"{symbol}: 빈 DataFrame")
                continue
            
            # 데이터 복사
            df = raw_data.copy()
            
            # 최소 필수 컬럼 확인
            essential_columns = ['Close']
            missing_essential = [col for col in essential_columns if col not in df.columns]
            
            if missing_essential:
                failed_symbols.append(f"{symbol}: 필수 컬럼 누락 - {missing_essential}")
                continue
            
            # 데이터 길이 확인
            if len(df) < 30:  # 최소 30일 데이터로 완화
                failed_symbols.append(f"{symbol}: 데이터 부족 ({len(df)}일)")
                continue
            
            # 1. 고급 기술적 지표 추가
            df = create_enhanced_features(df)
            
            # 2. 기본 기술적 점수 계산
            technical_score = calculate_technical_score(df)
            df['Technical_Score'] = technical_score
            
            # 3. 향상된 기술적 점수 계산
            enhanced_technical_score = calculate_enhanced_technical_score(df)
            df['Enhanced_Technical_Score'] = enhanced_technical_score
            
            # 4. 복합 점수 생성
            composite_score, future_returns_dict = create_composite_score(df)
            df['Composite_Score'] = composite_score
            
            # 5. 미래 수익률 저장 (검증용)
            for key, value in future_returns_dict.items():
                column_name = f'Future_{key.replace("future_", "")}'
                df[column_name] = value
            
            # 6. 라벨 생성 (복합 점수가 유효한 경우에만)
            valid_composite = composite_score.dropna()
            if len(valid_composite) > 0:
                labels = score_to_label(composite_score)
                df['Label'] = labels
                
                # 7. 라벨 이름 추가
                label_names = {0: 'Strong_Sell', 1: 'Hold', 2: 'Strong_Buy'}
                df['Label_Name'] = df['Label'].map(label_names)
                
                # 8. 라벨 분포 확인
                label_dist = df['Label'].value_counts().sort_index()
                if debug_mode:
                    print(f"   라벨 분포: {dict(label_dist)}")
            else:
                df['Label'] = 1  # 모두 홀드로 설정
                df['Label_Name'] = 'Hold'
                if debug_mode:
                    print(f"   복합 점수 없음 - 모두 Hold로 설정")
            
            # 9. 결과 저장
            enhanced_cryptos[symbol] = df
            
            # 10. CSV 저장 (옵션)
            try:
                output_file = f"{save_path}/{symbol}_enhanced.csv"
                df.to_csv(output_file, index=True)
            except Exception as e:
                print(f"⚠️ {symbol}: CSV 저장 실패 - {e}")
            
        except Exception as e:
            failed_symbols.append(f"{symbol}: 처리 중 오류 - {str(e)[:100]}")
            if debug_mode:
                print(f"❌ {symbol}: 상세 오류 - {e}")
            continue
    
    # 결과 요약
    success_count = len(enhanced_cryptos)
    total_count = len(symbols_to_process)
    failure_count = total_count - success_count
    
    print(f"\n{'='*50}")
    print(f"처리 완료!")
    print(f"✅ 성공: {success_count}개")
    print(f"❌ 실패: {failure_count}개")
    print(f"📁 저장 경로: {save_path}")
    
    if failed_symbols and debug_mode:
        print(f"\n실패한 심볼들:")
        for failed in failed_symbols[:10]:  # 처음 10개만 출력
            print(f"  - {failed}")
        if len(failed_symbols) > 10:
            print(f"  ... 및 {len(failed_symbols) - 10}개 더")
    
    return enhanced_cryptos

# 사용 예시 및 테스트
if __name__ == "__main__":
    # 사용 예시
    # enhanced_data = enhance_crypto_data_with_labels(crypto_data, test_symbols=['BTC', 'ETH'], debug_mode=True)
    
    # 전체 데이터 처리
    # enhanced_data = enhance_crypto_data_with_labels(crypto_data, debug_mode=False)
    pass