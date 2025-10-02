import pandas as pd
import numpy as np
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class CryptoDataLoader:
    """암호화폐 데이터 로더 유틸리티"""
    
    @staticmethod
    def load_cleaned_crypto_data(data_folder):
        """
        저장된 암호화폐 데이터를 로드
        
        Parameters:
        data_folder: 데이터가 저장된 폴더 경로
        
        Returns:
        tuple: (crypto_data, excluded_info, summary_info)
        - crypto_data: {symbol: DataFrame} 딕셔너리
        - excluded_info: 제외된 심볼 정보
        - summary_info: 요약 정보
        """
        print(f"📂 데이터 로딩 시작: {data_folder}")
        
        crypto_data = {}
        excluded_symbols = []
        loading_errors = []

        # with_strategies 폴더에서 전략 포함된 데이터 로드
        strategies_folder = os.path.join(data_folder)
        
        if not os.path.exists(strategies_folder):
            print(f"❌ 전략 데이터 폴더를 찾을 수 없습니다: {strategies_folder}")


            
            return {}, [], {}
        
        csv_files = [f for f in os.listdir(strategies_folder) if f.endswith('.csv')]
        
        if not csv_files:
            print("❌ CSV 파일을 찾을 수 없습니다!")
            return {}, [], {}
        
        print(f"📊 발견된 파일 수: {len(csv_files)}")
        
        # 각 파일 로드
        for csv_file in csv_files:
            symbol = csv_file.replace('.csv', '').split('_')[0]
            file_path = os.path.join(strategies_folder, csv_file)
            
            try:
                # CSV 로드
                df = pd.read_csv(file_path)
                
                # 날짜 컬럼 처리
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'])
                    df.set_index('Date', inplace=True)
                elif df.index.name != 'Date':
                    # 첫 번째 컬럼이 날짜인 경우
                    if pd.api.types.is_datetime64_any_dtype(df.iloc[:, 0]) or \
                       isinstance(df.iloc[0, 0], str) and len(df.iloc[0, 0]) > 8:
                        df.set_index(df.columns[0], inplace=True)
                        df.index = pd.to_datetime(df.index)
                        df.index.name = 'Date'
                
                # 데이터 정렬
                df = df.sort_index()
                
                # 최소 데이터 요구사항 체크
                if len(df) < 30:
                    excluded_symbols.append({
                        'symbol': symbol, 
                        'reason': f'데이터 부족 ({len(df)}일)',
                        'data_points': len(df)
                    })
                    continue
                
                # 필수 컬럼 체크
                required_columns = ['Open', 'High', 'Low', 'Close']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    excluded_symbols.append({
                        'symbol': symbol,
                        'reason': f'필수 컬럼 누락: {missing_columns}',
                        'data_points': len(df)
                    })
                    continue
                
                # 성공적으로 로드
                crypto_data[symbol] = df
                
            except Exception as e:
                loading_errors.append({
                    'symbol': symbol,
                    'error': str(e)
                })
                print(f"⚠️ {symbol} 로딩 실패: {e}")
        
        # 요약 정보 생성
        summary_info = CryptoDataLoader._generate_summary(crypto_data, excluded_symbols, loading_errors)
        
        # 결과 출력
        print(f"✅ 성공적으로 로드된 심볼: {len(crypto_data)}개")
        print(f"❌ 제외된 심볼: {len(excluded_symbols)}개")
        print(f"🔥 로딩 에러: {len(loading_errors)}개")
        
        return crypto_data, excluded_symbols, summary_info
    
    @staticmethod
    def _generate_summary(crypto_data, excluded_symbols, loading_errors):
        """요약 정보 생성"""
        if not crypto_data:
            return {
                'total_symbols': 0,
                'excluded_count': len(excluded_symbols),
                'error_count': len(loading_errors),
                'data_period': None,
                'avg_data_points': 0,
                'strategy_signals': 0
            }
        
        # 데이터 기간 계산
        all_start_dates = []
        all_end_dates = []
        total_data_points = 0
        strategy_signals = 0
        
        sample_df = list(crypto_data.values())[0]
        strategy_columns = [col for col in sample_df.columns if '_Signal' in col]
        strategy_signals = len(strategy_columns)
        
        for symbol, df in crypto_data.items():
            all_start_dates.append(df.index.min())
            all_end_dates.append(df.index.max())
            total_data_points += len(df)
        
        summary = {
            'total_symbols': len(crypto_data),
            'excluded_count': len(excluded_symbols),
            'error_count': len(loading_errors),
            'data_period': {
                'earliest_start': min(all_start_dates),
                'latest_end': max(all_end_dates)
            },
            'avg_data_points': total_data_points / len(crypto_data),
            'strategy_signals': strategy_signals,
            'total_columns': len(sample_df.columns),
            'excluded_reasons': {}
        }
        
        # 제외 사유별 통계
        for excluded in excluded_symbols:
            reason = excluded['reason']
            if reason not in summary['excluded_reasons']:
                summary['excluded_reasons'][reason] = 0
            summary['excluded_reasons'][reason] += 1
        
        return summary
    
    @staticmethod
    def get_data_info(crypto_data, detailed=False):
        """데이터 정보 출력"""
        if not crypto_data:
            print("❌ 로드된 데이터가 없습니다.")
            return
        
        print(f"\n📊 데이터 정보 요약")
        print("=" * 50)
        print(f"총 심볼 수: {len(crypto_data)}")
        
        # 샘플 데이터 정보
        sample_symbol = list(crypto_data.keys())[0]
        sample_df = crypto_data[sample_symbol]
        
        print(f"컬럼 수: {len(sample_df.columns)}")
        print(f"전략 시그널 수: {len([col for col in sample_df.columns if '_Signal' in col])}")
        
        # 데이터 기간
        all_start = min(df.index.min() for df in crypto_data.values())
        all_end = max(df.index.max() for df in crypto_data.values())
        print(f"데이터 기간: {all_start.date()} ~ {all_end.date()}")
        
        # 평균 데이터 포인트
        avg_points = np.mean([len(df) for df in crypto_data.values()])
        print(f"평균 데이터 포인트: {avg_points:.0f}일")
        
        if detailed:
            print(f"\n📋 심볼별 상세 정보:")
            for i, (symbol, df) in enumerate(crypto_data.items()):
                if i < 10:  # 처음 10개만 출력
                    print(f"  {symbol}: {len(df)}행, {df.index[0].date()} ~ {df.index[-1].date()}")
                elif i == 10:
                    print(f"  ... 및 {len(crypto_data) - 10}개 더")
                    break
        
        # 전략 시그널 정보
        signal_columns = [col for col in sample_df.columns if '_Signal' in col]
        if signal_columns:
            print(f"\n🎯 전략 시그널 목록:")
            strategy_groups = {
                '이동평균': [col for col in signal_columns if 'MA_' in col or 'EMA_' in col],
                'MACD': [col for col in signal_columns if 'MACD' in col],
                'RSI': [col for col in signal_columns if 'RSI' in col],
                '오실레이터': [col for col in signal_columns if any(x in col for x in ['Williams', 'CCI', 'Stoch'])],
                '가격패턴': [col for col in signal_columns if any(x in col for x in ['Candlestick', 'Shadow', 'Pivot'])],
                '거래량': [col for col in signal_columns if any(x in col for x in ['MFI', 'Volume'])],
                '모멘텀': [col for col in signal_columns if any(x in col for x in ['Momentum', 'Volatility'])],
                '복합': [col for col in signal_columns if 'Composite' in col or 'Final' in col]
            }
            
            for group, strategies in strategy_groups.items():
                if strategies:
                    print(f"  {group}: {len(strategies)}개")
    
    @staticmethod
    def load_ml_dataset(data_folder):
        """머신러닝 데이터셋 로드"""
        ml_file = os.path.join(data_folder, "ml_dataset_with_strategies.csv")
        
        if not os.path.exists(ml_file):
            print(f"❌ ML 데이터셋을 찾을 수 없습니다: {ml_file}")
            return None
        
        try:
            df = pd.read_csv(ml_file)
            
            # Date 컬럼이 있으면 datetime으로 변환
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
            
            print(f"✅ ML 데이터셋 로드 완료: {len(df)}행, {len(df.columns)}개 특성")
            
            # 타겟 분포 확인
            if 'Target_Label' in df.columns:
                target_dist = df['Target_Label'].value_counts().sort_index()
                print(f"📊 타겟 분포 - SELL(0): {target_dist.get(0, 0)}, HOLD(1): {target_dist.get(1, 0)}, BUY(2): {target_dist.get(2, 0)}")
            
            return df
            
        except Exception as e:
            print(f"❌ ML 데이터셋 로드 실패: {e}")
            return None

# 편의 함수들
def load_cleaned_crypto_data(data_folder):
    """간단한 래퍼 함수"""
    return CryptoDataLoader.load_cleaned_crypto_data(data_folder)

def load_ml_dataset(data_folder):
    """ML 데이터셋 로드 래퍼 함수"""
    return CryptoDataLoader.load_ml_dataset(data_folder)

def get_data_info(crypto_data, detailed=False):
    """데이터 정보 출력 래퍼 함수"""
    return CryptoDataLoader.get_data_info(crypto_data, detailed)

