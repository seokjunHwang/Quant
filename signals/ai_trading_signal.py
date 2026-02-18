"""
자동 트레이딩 시그널 생성 시스템
- 🔥 11개 주요 종목만 감시 (BTC, ETH, SHIB, DOT, BCH, AVAX, LINK, ADA, AAVE, TAO, SEI)
- 동일한 날짜 + 동일종목은 덮어씌우도록 로직구현 (일봉이니까)
- 정기적으로 신규 데이터 수집
- 모델 예측 수행
- MySQL 데이터베이스에 시그널 저장
"""
import schedule
import time
import pickle
import json
import mysql.connector
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from crypto_preprocessor import CryptoPreprocessor
import warnings
warnings.filterwarnings('ignore')


class AutoTradingSignal:
    """자동 트레이딩 시그널 생성기"""
    
    def __init__(self, model_path, db_config):
        """
        Args:
            model_path: 학습된 모델 파일 경로 (.pkl)
            db_config: MySQL 데이터베이스 연결 설정 (dict)
        """
        self.model_path = model_path
        self.db_config = db_config
        self.preprocessor = CryptoPreprocessor()
        self.model = None
        self.load_model()
        
        # 🔥 11개 주요 종목만 감시
        self.symbols = [
            'BTC',   # BTC + WBTC 통합
            'ETH',   # ETH + WETH + STETH + WSTETH 통합
            'SHIB',  # 1000SHIBUSDT
            'DOT',
            'BCH',
            'AVAX',
            'LINK',
            'ADA',
            'AAVE',
            'TAO',
            'SEI',
        ]

        # # 더 잘나오는 종목 순 8개 감시
        # self.symbols = [
        #     'BTC',   # BTC + WBTC 통합
        #     'ETH',   # ETH + WETH + STETH + WSTETH 통합
        #     'SHIB',  # 1000SHIBUSDT
        #     'DOT',
        #     'BCH',
        #     'AVAX',
        #     'LINK',
        #     'ADA',
        # ]


        print(f"자동 트레이딩 시그널 시스템 초기화 완료")
        print(f"감시 종목 ({len(self.symbols)}개): {', '.join(self.symbols)}")
    
    def load_model(self):
        """학습된 모델 로드"""
        try:
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)
            print(f"모델 로드 완료: {self.model_path}")
        except Exception as e:
            print(f"모델 로드 실패: {e}")
            raise
    
    def connect_db(self):
        """MySQL 데이터베이스 연결"""
        try:
            conn = mysql.connector.connect(**self.db_config)
            return conn
        except Exception as e:
            print(f"DB 연결 실패: {e}")
            return None
    
    def predict_signal(self, symbol):
        """
        단일 종목에 대한 예측 수행
        
        Args:
            symbol: 종목 심볼 (예: 'BTC')
            
        Returns:
            dict: 예측 결과 {'symbol', 'signal_type', 'confidence', 'price', 'features'}
        """
        try:
            # 1. 전처리
            features_df = self.preprocessor.preprocess_for_prediction(symbol)
            
            if features_df is None or features_df.empty:
                print(f"{symbol}: 전처리 실패")
                return None
            
            # 2. 예측
            features_array = features_df.values
            prediction = self.model.predict(features_array)
            prediction_proba = self.model.predict_proba(features_array)
            
            # 3. 시그널 타입 결정 (0: SHORT, 1: HOLD, 2: LONG)
            signal_map = {0: 'SHORT', 1: 'HOLD', 2: 'LONG'}
            predicted_class = int(prediction[0])
            signal_type = signal_map[predicted_class]
            
            # 4. 신뢰도 = 모델 확신도 (최대 확률값)
            confidence = float(np.max(prediction_proba))
            prediction_probability = float(prediction_proba[0][predicted_class])
            
            # 5. 현재 가격 정보
            price_df = self.preprocessor.fetch_latest_data(symbol, days=1)
            current_price = float(price_df['Close'].iloc[-1]) if not price_df.empty else None
            
            # 6. 바이낸스 심볼 변환
            binance_symbol = self.get_binance_symbol(symbol)
            
            result = {
                'symbol': binance_symbol,
                'signal_type': signal_type,
                'confidence': confidence,
                'prediction_probability': prediction_probability,
                'price': current_price,
                'features': features_df.to_dict('records')[0],
                'timestamp': datetime.now()
            }
            
            print(f"{symbol} -> {binance_symbol}: {signal_type} (신뢰도: {confidence:.2%})")
            return result
            
        except Exception as e:
            print(f"{symbol} 예측 실패: {e}")
            return None
    
    def get_binance_symbol(self, symbol):
        """야후 심볼을 바이낸스 선물 심볼로 변환"""
        binance_mapping = {
            'BTC': 'BTCUSDT',
            'ETH': 'ETHUSDT',
            'SHIB': '1000SHIBUSDT',
            'DOT': 'DOTUSDT',
            'BCH': 'BCHUSDT',
            'AVAX': 'AVAXUSDT',
            'LINK': 'LINKUSDT',
            'ADA': 'ADAUSDT',
            'AAVE': 'AAVEUSDT',
            'TAO': 'TAOUSDT',
            'SEI': 'SEIUSDT',
        }
        return binance_mapping.get(symbol, f"{symbol}USDT")
    
    def save_to_database(self, signal_data):
        """
        예측 결과를 MySQL에 저장 (같은 날짜+종목이면 UPDATE)
        
        Args:
            signal_data: predict_signal()의 반환값
        """
        if signal_data is None:
            return False
        
        conn = self.connect_db()
        if conn is None:
            return False
        
        try:
            cursor = conn.cursor()
            today = signal_data['timestamp'].date()
            
            # 기존 레코드 확인
            check_query = """
            SELECT id FROM trading_signals
            WHERE symbol = %s 
            AND strategy_name = 'AI_XGBOOST_PREDICTION'
            AND DATE(created_at) = %s
            """
            cursor.execute(check_query, (signal_data['symbol'], today))
            existing = cursor.fetchone()
            
            if existing:
                # UPDATE (덮어쓰기)
                update_query = """
                UPDATE trading_signals SET
                    signal_type = %s,
                    price = %s,
                    confidence = %s,
                    prediction_probability = %s,
                    features_data = %s,
                    message = %s,
                    created_at = %s,
                    processed = FALSE
                WHERE id = %s
                """
                values = (
                    signal_data['signal_type'],
                    signal_data['price'],
                    signal_data['confidence'],
                    signal_data['prediction_probability'],
                    json.dumps(signal_data['features'], default=str),
                    f"Updated at {signal_data['timestamp'].strftime('%H:%M:%S')}",
                    signal_data['timestamp'],
                    existing[0]
                )
                cursor.execute(update_query, values)
                print(f"   ✅ DB 업데이트: {signal_data['symbol']}")
                
            else:
                # INSERT (신규)
                insert_query = """
                INSERT INTO trading_signals 
                (strategy_name, symbol, timeframe, signal_type, signal_source, 
                 price, confidence, prediction_probability, features_data, 
                 model_version, message, created_at, processed)
                VALUES 
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                values = (
                    'AI_XGBOOST_PREDICTION',
                    signal_data['symbol'],
                    '1d',
                    signal_data['signal_type'],
                    'AI_MODEL',
                    signal_data['price'],
                    signal_data['confidence'],
                    signal_data['prediction_probability'],
                    json.dumps(signal_data['features'], default=str),
                    'v1.0',
                    f"Created at {signal_data['timestamp'].strftime('%H:%M:%S')}",
                    signal_data['timestamp'],
                    False
                )
                cursor.execute(insert_query, values)
                print(f"   ✅ DB 신규 생성: {signal_data['symbol']}")
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            print(f"   ❌ DB 저장 실패: {e}")
            conn.rollback()
            cursor.close()
            conn.close()
            return False
    
    def run_prediction_all(self):
        """
        모든 종목에 대한 예측 실행
        """
        print("\n" + "="*70)
        print(f"🤖 AI 예측 사이클 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        success_count = 0
        fail_count = 0
        
        for symbol in self.symbols:
            try:
                print(f"\n📊 {symbol} 분석 중...")
                
                # 예측 수행
                signal_data = self.predict_signal(symbol)
                
                # DB 저장
                if signal_data:
                    if self.save_to_database(signal_data):
                        success_count += 1
                    else:
                        fail_count += 1
                else:
                    fail_count += 1
                    
                time.sleep(1)  # API 부하 방지
                
            except Exception as e:
                print(f"   ❌ {symbol} 처리 중 오류: {e}")
                fail_count += 1
        
        print("\n" + "="*70)
        print(f"✅ 예측 완료: 성공 {success_count}개, 실패 {fail_count}개")
        print("="*70 + "\n")
        
        return success_count, fail_count
    
    def start_scheduler(self, run_time="09:00"):
        """
        스케줄러 시작 (매일 지정된 시간에 실행)
        
        Args:
            run_time: 실행 시간 (HH:MM 형식, 기본값 09:00)
        """
        print(f"\n{'='*70}")
        print(f"📅 자동 시그널 생성 스케줄러 시작")
        print(f"{'='*70}")
        print(f"⏰ 실행 시간: 매일 {run_time}")
        print(f"📊 감시 종목: {len(self.symbols)}개")
        print(f"{'='*70}")
        print("📌 Ctrl+C를 눌러 스케줄러를 중단할 수 있습니다.\n")
        
        # 스케줄 등록
        schedule.every().day.at(run_time).do(self.run_prediction_all)
        
        # 즉시 1회 실행
        print("🚀 초기 예측 실행...\n")
        self.run_prediction_all()
        
        # 스케줄러 실행
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 1분마다 체크
                
        except KeyboardInterrupt:
            print(f"\n\n{'='*70}")
            print(f"🛑 스케줄러 중단됨")
            print(f"{'='*70}\n")
    
    def run_once(self):
        """
        1회만 실행 (테스트용)
        """
        print(f"\n{'='*70}")
        print(f"🧪 단일 실행 모드")
        print(f"{'='*70}\n")
        
        self.run_prediction_all()


def main():
    """메인 함수"""
    
    # 설정
    model_path = "models/xgboost_crypto_model.pkl"  # 모델 경로 수정 필요
    db_config = {
        'host': 'localhost',
        'database': 'trading_signals',
        'user': 'root',
        'password': 'ghkd2759A!'
    }
    
    print("\n" + "="*70)
    print("🤖 AI 자동 트레이딩 시그널 생성 시스템")
    print("   (11개 주요 종목 감시: BTC, ETH, SHIB, DOT, BCH, AVAX,")
    print("    LINK, ADA, AAVE, TAO, SEI)")
    print("="*70)
    
    try:
        # 시스템 초기화
        auto_signal = AutoTradingSignal(model_path, db_config)
        
        # 사용자 선택
        print("\n" + "="*70)
        print("📌 실행 모드를 선택하세요:")
        print("="*70)
        print("1. 스케줄러 시작 (매일 09:00에 자동 실행)")
        print("2. 즉시 1회 실행 (테스트)")
        print("3. 커스텀 시간 설정 스케줄러")
        print("0. 종료")
        print("="*70)
        
        choice = input("\n선택 (0-3): ").strip()
        
        if choice == '1':
            auto_signal.start_scheduler(run_time="09:00")
            
        elif choice == '2':
            auto_signal.run_once()
            
        elif choice == '3':
            custom_time = input("\n실행 시간을 입력하세요 (HH:MM 형식, 예: 14:30): ").strip()
            try:
                # 시간 형식 검증
                datetime.strptime(custom_time, '%H:%M')
                auto_signal.start_scheduler(run_time=custom_time)
            except ValueError:
                print("\n❌ 잘못된 시간 형식입니다. HH:MM 형식으로 입력해주세요.")
            
        elif choice == '0':
            print("\n👋 프로그램을 종료합니다.")
            
        else:
            print("\n❌ 잘못된 선택입니다.")
    
    except FileNotFoundError:
        print(f"\n❌ 모델 파일을 찾을 수 없습니다: {model_path}")
        print("   모델 파일 경로를 확인해주세요.")
    
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()