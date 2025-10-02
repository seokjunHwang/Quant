import pandas as pd
import numpy as np
import os
from sklearn.preprocessing import StandardScaler, RobustScaler
import joblib
import warnings
warnings.filterwarnings('ignore')


def debug_infinite_values(df, step_name):
    """무한값 디버깅 함수"""
    inf_cols = []
    for col in df.select_dtypes(include=[np.number]).columns:
        if np.isinf(df[col]).any():
            inf_count = np.isinf(df[col]).sum()
            inf_cols.append(f"{col}: {inf_count}개")
    
    if inf_cols:
        print(f"🚨 {step_name}에서 무한값 발견:")
        for col_info in inf_cols:
            print(f"  - {col_info}")
    return len(inf_cols) > 0

class XGBoostStockPreprocessor:
    """XGBoost 학습을 위한 종목별 정규화 전처리기"""
    
    def __init__(self, forecast_horizon=1):
        self.forecast_horizon = forecast_horizon
        self.symbol_stats = {}
        self.global_scalers = {}
        
    def calculate_symbol_statistics(self, processed_stocks):
        """종목별 기본 통계 계산"""
        print("종목별 통계 계산 중...")
        
        for symbol, df in processed_stocks.items():
            # 안전한 통계 계산 (0 방지)
            close_values = df['Close'].replace(0, np.nan).dropna()
            volume_values = df['Volume'].replace(0, np.nan).dropna() if 'Volume' in df.columns else pd.Series([1])
            
            stats = {
                'avg_close': close_values.mean() if len(close_values) > 0 else 1.0,
                'close_std': close_values.std() if len(close_values) > 0 else 1.0,
                'avg_volume': volume_values.mean() if len(volume_values) > 0 else 1.0,
                'volatility': close_values.pct_change().std() * np.sqrt(252) if len(close_values) > 1 else 0.1,
                'price_level': 'high' if close_values.mean() > 100 else 'low'
            }
            
            # NaN 방지
            for key, value in stats.items():
                if pd.isna(value) or value == 0:
                    if 'avg' in key or 'std' in key:
                        stats[key] = 1.0
                    else:
                        stats[key] = 0.1
                        
            self.symbol_stats[symbol] = stats
        
        print(f"  처리된 종목 수: {len(self.symbol_stats)}")
    
    def create_price_features(self, df, symbol):
        """가격 기반 피쳐 생성 (로그 수익률 중심) - 무한값 방지"""
        df_processed = df.copy()
        
        # 0값들을 매우 작은 값으로 대체 (무한값 방지)
        price_columns = ['Close', 'Open', 'High', 'Low']
        for col in price_columns:
            if col in df.columns:
                df_processed[col] = df_processed[col].replace(0, 1e-8)
        
        # 1. 로그 수익률 계산 (안전하게)
        for col in price_columns:
            if col in df.columns:
                # 로그 수익률 (안전한 계산)
                price_ratio = df_processed[col] / df_processed[col].shift(1)
                price_ratio = price_ratio.replace([0, np.inf, -np.inf], np.nan)
                price_ratio = price_ratio.clip(lower=1e-10, upper=1e10)  # 극값 제한
                df_processed[f'{col}_log_return'] = np.log(price_ratio)
                
                # 단순 수익률
                df_processed[f'{col}_return'] = df_processed[col].pct_change()
        
        # 2. 이동평균들을 현재가 대비 비율로 변환 (새로운 MA 기간들 포함)
        ma_columns = [col for col in df.columns if col.startswith('MA_') and col != 'MACD']
        for col in ma_columns:
            if col in df.columns:
                # 0값 방지
                ma_values = df_processed[col].replace(0, 1e-8)
                close_values = df_processed['Close'].replace(0, 1e-8)
                
                df_processed[f'{col}_ratio'] = ma_values / close_values
                df_processed[f'{col}_distance'] = (close_values - ma_values) / close_values
        
        # 3. EMA들도 비율로 변환 (새로운 EMA 기간들 포함)
        ema_columns = [col for col in df.columns if col.startswith('EMA_')]
        for col in ema_columns:
            if col in df.columns:
                ema_values = df_processed[col].replace(0, 1e-8)
                close_values = df_processed['Close'].replace(0, 1e-8)
                df_processed[f'{col}_ratio'] = ema_values / close_values
        
        # 4. 볼린저 밴드를 상대적 위치로 변환
        if 'BB_Upper_20' in df.columns and 'BB_Lower_20' in df.columns:
            # 볼린저밴드 폭 계산 (0 방지)
            bb_width = df_processed['BB_Upper_20'] - df_processed['BB_Lower_20']
            bb_width = bb_width.replace(0, 1e-8)
            
            # 볼린저밴드 내 상대적 위치
            df_processed['BB_relative_position'] = (
                (df_processed['Close'] - df_processed['BB_Lower_20']) / bb_width
            ).fillna(0.5)
            
            # 각 밴드 대비 거리 (안전하게)
            close_values = df_processed['Close'].replace(0, 1e-8)
            df_processed['BB_upper_distance'] = (df_processed['BB_Upper_20'] - close_values) / close_values
            df_processed['BB_lower_distance'] = (close_values - df_processed['BB_Lower_20']) / close_values
        
        # 5. 거래량 정규화 (안전하게)
        if 'Volume' in df.columns:
            avg_volume = self.symbol_stats[symbol]['avg_volume']
            volume_values = df_processed['Volume'].replace(0, 1e-8)
            
            df_processed['Volume_normalized'] = volume_values / avg_volume
            df_processed['Volume_log_ratio'] = np.log(volume_values / avg_volume + 1e-8)
        
        # 무한값 및 극값 처리
        numeric_columns = df_processed.select_dtypes(include=[np.number]).columns
        for col in numeric_columns:
            df_processed[col] = df_processed[col].replace([np.inf, -np.inf], np.nan)
            if df_processed[col].notna().sum() > 0:
                # 극값 클리핑 (99.9% / 0.1% percentile)
                p99 = df_processed[col].quantile(0.999)
                p01 = df_processed[col].quantile(0.001)
                if not pd.isna(p99) and not pd.isna(p01):
                    df_processed[col] = df_processed[col].clip(lower=p01, upper=p99)
        
        return df_processed
    
    def create_technical_features(self, df):
        """기술적 지표 기반 추가 피쳐 생성"""
        df_enhanced = df.copy()
        
        # 1. RSI 기반 피쳐 (다양한 기간의 RSI 처리)
        rsi_columns = [col for col in df.columns if col.startswith('RSI_')]
        for rsi_col in rsi_columns:
            if rsi_col in df.columns:
                df_enhanced[f'{rsi_col}_overbought'] = (df[rsi_col] > 70).astype(int)
                df_enhanced[f'{rsi_col}_oversold'] = (df[rsi_col] < 30).astype(int)
                df_enhanced[f'{rsi_col}_normalized'] = (df[rsi_col] - 50) / 50  # -1 to 1 범위
        
        # 2. MACD 기반 피쳐 (다양한 MACD 변형들 처리)
        macd_columns = [col for col in df.columns if col.startswith('MACD') and not col.endswith('_Signal')]
        for macd_col in macd_columns:
            signal_col = f'{macd_col}_Signal'
            if macd_col in df.columns and signal_col in df.columns:
                df_enhanced[f'{macd_col}_above_signal'] = (df[macd_col] > df[signal_col]).astype(int)
                df_enhanced[f'{macd_col}_signal_distance'] = df[macd_col] - df[signal_col]
        
        # 3. 스토캐스틱 기반 피쳐 (다양한 기간 처리)
        stoch_k_columns = [col for col in df.columns if col.startswith('Stoch_K_')]
        for k_col in stoch_k_columns:
            period = k_col.replace('Stoch_K_', '')
            d_col = f'Stoch_D_{period}'
            if k_col in df.columns and d_col in df.columns:
                df_enhanced[f'Stoch_{period}_K_above_D'] = (df[k_col] > df[d_col]).astype(int)
                df_enhanced[f'Stoch_{period}_overbought'] = ((df[k_col] > 80) & (df[d_col] > 80)).astype(int)
                df_enhanced[f'Stoch_{period}_oversold'] = ((df[k_col] < 20) & (df[d_col] < 20)).astype(int)
        
        # 4. Williams %R 기반 피쳐 (다양한 기간 처리)
        williams_columns = [col for col in df.columns if col.startswith('Williams_R_')]
        for wr_col in williams_columns:
            if wr_col in df.columns:
                df_enhanced[f'{wr_col}_overbought'] = (df[wr_col] > -20).astype(int)
                df_enhanced[f'{wr_col}_oversold'] = (df[wr_col] < -80).astype(int)
        
        # 5. CCI 기반 피쳐 (다양한 기간 처리)
        cci_columns = [col for col in df.columns if col.startswith('CCI_')]
        for cci_col in cci_columns:
            if cci_col in df.columns:
                df_enhanced[f'{cci_col}_overbought'] = (df[cci_col] > 100).astype(int)
                df_enhanced[f'{cci_col}_oversold'] = (df[cci_col] < -100).astype(int)
        
        # 6. 변동성 피쳐 (안전하게)
        if 'Close_log_return' in df_enhanced.columns:
            # 실현 변동성 (rolling) - NaN 처리
            log_returns = df_enhanced['Close_log_return'].fillna(0)
            df_enhanced['realized_volatility_5'] = log_returns.rolling(5, min_periods=1).std()
            df_enhanced['realized_volatility_20'] = log_returns.rolling(20, min_periods=1).std()
            
            # 변동성 레짐 (고변동성/저변동성)
            vol_20 = df_enhanced['realized_volatility_20'].fillna(0)
            vol_median = vol_20.median() if vol_20.sum() > 0 else 0
            df_enhanced['high_volatility_regime'] = (vol_20 > vol_median).astype(int)
        
        # 7. 추세 강도 피쳐
        if 'MA_20_ratio' in df_enhanced.columns and 'MA_50_ratio' in df_enhanced.columns:
            df_enhanced['trend_strength'] = df_enhanced['MA_20_ratio'] - df_enhanced['MA_50_ratio']
            df_enhanced['strong_uptrend'] = (df_enhanced['trend_strength'] > 0.02).astype(int)
            df_enhanced['strong_downtrend'] = (df_enhanced['trend_strength'] < -0.02).astype(int)
        
        return df_enhanced
    
    def create_time_features(self, df):
        """시간 기반 피쳐 생성"""
        df_time = df.copy()
        
        # Date 컬럼 확실히 생성
        if isinstance(df.index, pd.DatetimeIndex):
            df_time['Date'] = df.index
            dates = df.index
        elif 'Date' in df.columns:
            dates = pd.to_datetime(df['Date'])
        else:
            return df_time
        
        df_time['year'] = dates.year
        df_time['month'] = dates.month
        df_time['quarter'] = dates.quarter
        df_time['day_of_week'] = dates.dayofweek
        df_time['is_month_start'] = dates.is_month_start.astype(int)
        df_time['is_month_end'] = dates.is_month_end.astype(int)
        df_time['is_quarter_start'] = dates.is_quarter_start.astype(int)
        df_time['is_quarter_end'] = dates.is_quarter_end.astype(int)
        
        # 순환 인코딩 (월, 요일)
        df_time['month_sin'] = np.sin(2 * np.pi * df_time['month'] / 12)
        df_time['month_cos'] = np.cos(2 * np.pi * df_time['month'] / 12)
        df_time['dow_sin'] = np.sin(2 * np.pi * df_time['day_of_week'] / 7)
        df_time['dow_cos'] = np.cos(2 * np.pi * df_time['day_of_week'] / 7)
        
        return df_time
    
    def prepare_single_symbol(self, df, symbol):
        """단일 종목 데이터 전처리"""
        # 1. 가격 기반 피쳐 생성
        df_price = self.create_price_features(df, symbol)
        
        # 2. 기술적 지표 피쳐 생성
        df_technical = self.create_technical_features(df_price)
        
        # 3. 시간 피쳐 생성
        df_complete = self.create_time_features(df_technical)
        
        # 4. 타겟 라벨 생성 (Future_Label 생성)
        if 'Optimized_Label' in df_complete.columns:
            df_complete['Future_Label'] = df_complete['Optimized_Label'].shift(-self.forecast_horizon)
        else:
            print("no Optimized_label... : 2차라벨 생성이 안되었습니다.")
        
        # 5. 종목 정보 추가
        df_complete['Symbol'] = symbol
        
        return df_complete
    
    def apply_global_scaling(self, combined_df):
        """전체 데이터에 대한 글로벌 스케일링"""
        df_scaled = combined_df.copy()
        
        # 스케일링 전 무한값 및 이상치 처리
        print("무한값 및 이상치 처리 중...")
        
        # 1. 무한값을 NaN으로 변환
        df_scaled = df_scaled.replace([np.inf, -np.inf], np.nan)
        
        # 2. 매우 큰 값들 클리핑 (99.9% percentile 기준)
        numeric_cols = df_scaled.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if df_scaled[col].notna().sum() > 0:  # 데이터가 있는 경우만
                p99 = df_scaled[col].quantile(0.999)
                p01 = df_scaled[col].quantile(0.001)
                if not pd.isna(p99) and not pd.isna(p01) and p99 != p01:
                    df_scaled[col] = df_scaled[col].clip(lower=p01, upper=p99)
        
        # 3. 남은 NaN 처리 (스케일링 전에)
        df_scaled = df_scaled.fillna(0)
        
        print(f"  처리 후 무한값 수: {np.isinf(df_scaled.select_dtypes(include=[np.number])).sum().sum()}")
        
        # 문자열 컬럼들 먼저 식별
        string_columns = df_scaled.select_dtypes(include=['object']).columns.tolist()
        
        # 스케일링할 피쳐 그룹 분류
        log_return_features = [col for col in df_scaled.columns if '_log_return' in col]
        return_features = [col for col in df_scaled.columns if '_return' in col and '_log_return' not in col]
        ratio_features = [col for col in df_scaled.columns if '_ratio' in col]
        distance_features = [col for col in df_scaled.columns if '_distance' in col]
        volatility_features = [col for col in df_scaled.columns if 'volatility' in col or 'Volatility' in col]
        
        # SIGNAL_FEATURES에 정의된 정규화 제외 특성들
        normalized_features = SIGNAL_FEATURES.copy()
        
        # 나머지 기술적 지표들
        exclude_cols = (EXCLUDE_FROM_TRAINING + log_return_features + return_features + 
                    ratio_features + distance_features + volatility_features + normalized_features +
                    ['year', 'month', 'quarter', 'day_of_week'] + string_columns)
        
        other_features = [col for col in df_scaled.columns if col not in exclude_cols]
        
        # 스케일러 초기화
        if not self.global_scalers:
            self.global_scalers = {
                'log_return_scaler': StandardScaler(),
                'return_scaler': RobustScaler(quantile_range=(1, 99)),
                'ratio_scaler': StandardScaler(),
                'distance_scaler': StandardScaler(),
                'volatility_scaler': RobustScaler(quantile_range=(5, 95)),
                'other_scaler': StandardScaler()
            }
        
        # 각 그룹별 스케일링 (안전하게)
        def safe_scaling(scaler, data, feature_names, scaler_name):
            if feature_names and len(feature_names) > 0:
                clean_data = data[feature_names].fillna(0)
                # 추가 무한값 체크
                if np.isinf(clean_data).any().any():
                    print(f"  ⚠️ {scaler_name}에서 무한값 발견, 0으로 대체")
                    clean_data = clean_data.replace([np.inf, -np.inf], 0)
                
                try:
                    scaled_values = scaler.fit_transform(clean_data)
                    data[feature_names] = scaled_values
                    print(f"  ✅ {scaler_name}: {len(feature_names)}개 피쳐 스케일링 완료")
                except Exception as e:
                    print(f"  ❌ {scaler_name} 스케일링 실패: {e}")
                    # 실패시 0으로 대체
                    data[feature_names] = 0
            return data
        
        df_scaled = safe_scaling(self.global_scalers['log_return_scaler'], df_scaled, 
                               log_return_features, "로그수익률")
        df_scaled = safe_scaling(self.global_scalers['return_scaler'], df_scaled, 
                               return_features, "일반수익률")
        df_scaled = safe_scaling(self.global_scalers['ratio_scaler'], df_scaled, 
                               ratio_features, "비율")
        df_scaled = safe_scaling(self.global_scalers['distance_scaler'], df_scaled, 
                               distance_features, "거리")
        df_scaled = safe_scaling(self.global_scalers['volatility_scaler'], df_scaled, 
                               volatility_features, "변동성")
        df_scaled = safe_scaling(self.global_scalers['other_scaler'], df_scaled, 
                               other_features, "기타지표")
        
        return df_scaled
    
    def get_training_features(self, df):
        """학습에 사용할 피쳐만 선택"""
        all_columns = df.columns.tolist()
        training_features = [col for col in all_columns if col not in EXCLUDE_FROM_TRAINING]
        return training_features
    
    def process_all_stocks(self, processed_stocks, output_dir):
        """전체 종목 처리 및 데이터 분할"""
        print("XGBoost용 데이터 전처리 시작")
        print("=" * 60)
        
        # 1. 종목별 통계 계산
        self.calculate_symbol_statistics(processed_stocks)
        
        # 2. 종목별 전처리
        all_data = []
        backtest_data = {}
        
        print("\n종목별 전처리 중...")
        for symbol, df in processed_stocks.items():
            print(f"  처리 중: {symbol}")
            
            # 백테스팅용 원본 데이터 보존 (Date 처리)
            df_reset = df.reset_index()
            if 'Date' not in df_reset.columns and 'index' in df_reset.columns:
                df_reset.rename(columns={'index': 'Date'}, inplace=True)
            
            # BACKTEST_PRESERVE_COLUMNS에 있는 컬럼들만 선택
            available_cols = [col for col in BACKTEST_PRESERVE_COLUMNS if col in df_reset.columns]
            backtest_data[symbol] = df_reset[available_cols].copy()
            
            # 학습용 데이터 전처리
            processed_df = self.prepare_single_symbol(df, symbol)
            all_data.append(processed_df)
        
        # 3. 모든 데이터 합치기
        combined_df = pd.concat(all_data, axis=0, ignore_index=True)
        print(f"\n합친 데이터 크기: {combined_df.shape}")
        
        # 4. 글로벌 스케일링
        print("글로벌 스케일링 적용 중...")
        scaled_df = self.apply_global_scaling(combined_df)
        
        # 5. 최종 결측치 및 무한값 처리
        scaled_df = scaled_df.replace([np.inf, -np.inf], np.nan)
        scaled_df = scaled_df.dropna(subset=['Future_Label'])
        
        # 최종 결측치 처리
        numeric_columns = scaled_df.select_dtypes(include=[np.number]).columns
        scaled_df[numeric_columns] = scaled_df[numeric_columns].fillna(0)
        
        print(f"최종 데이터 크기: {scaled_df.shape}")
        
        # 6. 라벨 분포 확인
        print(f"\n라벨 분포:")
        label_counts = scaled_df['Future_Label'].value_counts().sort_index()
        for label, count in label_counts.items():
            label_name = {0: 'Sell', 1: 'Hold', 2: 'Buy'}[int(label)]
            print(f"  {int(label)} ({label_name}): {count:,}개 ({count/len(scaled_df)*100:.1f}%)")
        
        # 7. 학습용 피쳐 리스트
        training_features = self.get_training_features(scaled_df)
        print(f"\n학습용 피쳐 수: {len(training_features)}")
        
        # 8. 데이터 저장
        os.makedirs(output_dir, exist_ok=True)
        
        # 전체 데이터 (학습용)
        scaled_df.to_csv(os.path.join(output_dir, 'xgboost_training_data.csv'), index=False)
        
        # 백테스팅용 데이터 (종목별 개별 파일)
        backtest_dir = os.path.join(output_dir, 'backtest_data')
        os.makedirs(backtest_dir, exist_ok=True)
        
        for symbol, data in backtest_data.items():
            data.to_csv(os.path.join(backtest_dir, f'{symbol}_backtest.csv'), index=False)
        
        # 전처리기 저장
        joblib.dump(self, os.path.join(output_dir, 'xgboost_preprocessor.pkl'))
        
        # 피쳐 리스트 저장
        with open(os.path.join(output_dir, 'training_features.txt'), 'w') as f:
            for feature in training_features:
                f.write(f"{feature}\n")
        
        print(f"\n데이터 저장 완료:")
        print(f"  - 학습용: {output_dir}/xgboost_training_data.csv")
        print(f"  - 백테스팅용: {backtest_dir}/")
        print(f"  - 전처리기: {output_dir}/xgboost_preprocessor.pkl")
        print(f"  - 피쳐 리스트: {output_dir}/training_features.txt")
        
        return scaled_df, backtest_data, training_features

def split_time_series_data(df, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15):
    """시계열 데이터 시간순 분할"""
    
    # Date 기준 정렬
    if 'Date' in df.columns:
        df_sorted = df.sort_values('Date').copy()
    else:
        df_sorted = df.copy()
    
    n = len(df_sorted)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))
    
    train_df = df_sorted.iloc[:train_end].copy()
    val_df = df_sorted.iloc[train_end:val_end].copy()
    test_df = df_sorted.iloc[val_end:].copy()
    
    print(f"\n데이터 분할 결과:")
    print(f"  훈련: {len(train_df):,}개 ({len(train_df)/n*100:.1f}%)")
    print(f"  검증: {len(val_df):,}개 ({len(val_df)/n*100:.1f}%)")
    print(f"  테스트: {len(test_df):,}개 ({len(test_df)/n*100:.1f}%)")
    
    if 'Date' in df.columns:
        print(f"  기간: {train_df['Date'].min().date()} ~ {test_df['Date'].max().date()}")
    
    return train_df, val_df, test_df

def filter_target_symbols(processed_stocks, target_symbols=None):
    """
    타겟 종목들만 필터링
    
    Parameters:
    -----------
    processed_stocks : dict
        전체 종목별 데이터프레임
    target_symbols : list or None
        선택할 종목 리스트. None이면 전체 사용
        예: ['BTC', 'ETH', 'SOL'] (-USD 제외)
    
    Returns:
    --------
    dict : 필터링된 종목별 데이터프레임
    """
    if target_symbols is None:
        print("🔄 전체 종목 사용")
        return processed_stocks
    
    # -USD 제거하여 정규화
    normalized_targets = []
    for symbol in target_symbols:
        clean_symbol = symbol.replace('-USD', '').replace('_USDT', '').replace('USDT', '')
        normalized_targets.append(clean_symbol)
    
    # 사용 가능한 종목들 확인
    available_symbols = list(processed_stocks.keys())
    filtered_stocks = {}
    found_symbols = []
    missing_symbols = []
    
    for target in normalized_targets:
        # 정확히 일치하는 심볼 찾기
        matched = False
        for available in available_symbols:
            # 다양한 패턴 매칭
            clean_available = available.replace('-USD', '').replace('_USDT', '').replace('USDT', '')
            if clean_available == target or available == target:
                filtered_stocks[available] = processed_stocks[available]
                found_symbols.append(f"{target} → {available}")
                matched = True
                break
        
        if not matched:
            missing_symbols.append(target)
    
    # 결과 출력
    print(f"🎯 타겟 종목 필터링 결과:")
    print(f"  요청된 종목: {len(target_symbols)}개")
    print(f"  발견된 종목: {len(found_symbols)}개")
    
    if found_symbols:
        print("  ✅ 매칭된 종목들:")
        for match in found_symbols:
            print(f"    - {match}")
    
    if missing_symbols:
        print(f"  ❌ 찾을 수 없는 종목들: {missing_symbols}")
        print(f"  💡 사용 가능한 종목들: {list(processed_stocks.keys())[:10]}...")
    
    return filtered_stocks

# 메인 실행 함수
def prepare_xgboost_data(processed_stocks, output_dir='./data/xgboost', forecast_horizon=1, target_symbols=None):
    """
    XGBoost 학습을 위한 완전한 데이터 전처리
    
    Parameters:
    -----------
    processed_stocks : dict
        종목별 데이터프레임 (Final_Composite_Signal 포함)
    output_dir : str
        출력 디렉토리
    forecast_horizon : int
        예측 기간 (일)
    target_symbols : list or None
        선택할 종목 리스트. None이면 전체 사용
        예: ['BTC', 'ETH', 'SOL', 'DOGE'] (-USD는 자동 제거됨)
    
    Returns:
    --------
    dict : (학습용_데이터, 백테스팅용_데이터, 피쳐_리스트)
    """
    
    # 1. 타겟 종목 필터링
    filtered_stocks = filter_target_symbols(processed_stocks, target_symbols)
    
    if not filtered_stocks:
        raise ValueError("❌ 선택된 종목이 없습니다!")
    
    # 2. 전처리기 초기화
    preprocessor = XGBoostStockPreprocessor(forecast_horizon=forecast_horizon)
    
    # 3. 전체 데이터 처리
    scaled_df, backtest_data, training_features = preprocessor.process_all_stocks(
        filtered_stocks, output_dir
    )
    
    # 4. 시계열 분할
    train_df, val_df, test_df = split_time_series_data(scaled_df)
    
    # 5. 분할된 데이터 저장
    train_df.to_csv(os.path.join(output_dir, 'train_data.csv'), index=False)
    val_df.to_csv(os.path.join(output_dir, 'val_data.csv'), index=False)
    test_df.to_csv(os.path.join(output_dir, 'test_data.csv'), index=False)
    
    return {
        'train': train_df,
        'val': val_df, 
        'test': test_df,
        'backtest_data': backtest_data,
        'training_features': training_features,
        'preprocessor': preprocessor
    }