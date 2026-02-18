"""
자동 트레이딩 시그널 생성 시스템 - 실제 가격 적용 테스트
- 🔥 11개 주요 종목만 감시 (BTC, ETH, SHIB, DOT, BCH, AVAX, LINK, ADA, AAVE, TAO, SEI)
- 10초마다 시그널 생성
- 야후 파이낸스에서 실시간 가격 조회
- 동일한 날짜 + 동일종목은 덮어씌우도록 로직구현
"""
import time
import random
import json
import mysql.connector
from datetime import datetime
import warnings
import yfinance as yf
warnings.filterwarnings('ignore')


class AutoTradingSignalTest:
    """자동 트레이딩 시그널 테스트 생성기 (실제 가격 사용)"""
    
    def __init__(self, db_config):
        """
        Args:
            db_config: MySQL 데이터베이스 연결 설정 (dict)
        """
        self.db_config = db_config
        
        # # 🔥 11개 주요 종목 (야후 파이낸스 티커)
        # self.symbols = {
        #     'BTC': 'BTC-USD',      # BTC + WBTC 통합
        #     'ETH': 'ETH-USD',      # ETH + WETH + STETH + WSTETH 통합
        #     'SHIB': 'SHIB-USD',    # 1000SHIBUSDT
        #     'DOT': 'DOT-USD',
        #     'BCH': 'BCH-USD',
        #     'AVAX': 'AVAX-USD',
        #     'LINK': 'LINK-USD',
        #     'ADA': 'ADA-USD',
        #     'AAVE': 'AAVE-USD',
        #     'TAO': 'TAO22974-USD',
        #     'SEI': 'SEI-USD',
        # }
        
        # # 🔥 바이낸스 선물 심볼 매핑
        # self.binance_symbols = {
        #     'BTC': 'BTCUSDT',
        #     'ETH': 'ETHUSDT',
        #     'SHIB': '1000SHIBUSDT',  # SHIB는 1000배
        #     'DOT': 'DOTUSDT',
        #     'BCH': 'BCHUSDT',
        #     'AVAX': 'AVAXUSDT',
        #     'LINK': 'LINKUSDT',
        #     'ADA': 'ADAUSDT',
        #     'AAVE': 'AAVEUSDT',
        #     'TAO': 'TAOUSDT',
        #     'SEI': 'SEIUSDT',
        # }
        
        # 🔥 수정: 3개 종목만 (ETH, SHIB, ADA)
        self.symbols = {
            'ETH': 'ETH-USD',      # ETH + WETH + STETH + WSTETH 통합
            'SHIB': 'SHIB-USD',    # 1000SHIBUSDT
            'ADA': 'ADA-USD',
        }
        
        # 🔥 수정: 바이낸스 선물 심볼 매핑 (3개만)
        self.binance_symbols = {
            'ETH': 'ETHUSDT',
            'SHIB': '1000SHIBUSDT',  # SHIB는 1000배
            'ADA': 'ADAUSDT',
        }
        


        # 시그널 타입
        self.signal_types = ['LONG', 'SHORT', 'HOLD']
        
        # 가격 캐시 (API 호출 최소화)
        self.price_cache = {}
        self.last_price_update = None
        
        print("🧪 자동 트레이딩 시그널 테스트 시스템 초기화 완료")
        print(f"📊 감시 종목 ({len(self.symbols)}개): {', '.join(self.symbols.keys())}")
        print(f"💰 실제 가격: 야후 파이낸스 API 사용")
        print(f"⏱️  예측 사이클: 10초마다 전체 종목 시그널 생성\n")
    
    def connect_db(self):
        """MySQL 데이터베이스 연결"""
        try:
            conn = mysql.connector.connect(**self.db_config)
            return conn
        except Exception as e:
            print(f"❌ DB 연결 실패: {e}")
            return None
    
    def fetch_real_prices(self):
        """야후 파이낸스에서 실제 가격 조회"""
        try:
            print("💰 실제 가격 조회 중...")
            prices = {}
            
            for symbol, ticker in self.symbols.items():
                try:
                    # yfinance로 실시간 가격 조회
                    stock = yf.Ticker(ticker)
                    data = stock.history(period='1d')
                    
                    if not data.empty:
                        price = float(data['Close'].iloc[-1])
                        
                        # SHIB는 1000배 변환 (바이낸스는 1000SHIBUSDT 사용)
                        if symbol == 'SHIB':
                            price = price * 1000
                        
                        prices[symbol] = price
                        print(f"   ✅ {symbol:6s} ({self.binance_symbols[symbol]:15s}): ${price:>15,.6f}")
                    else:
                        print(f"   ❌ {symbol}: 데이터 없음")
                        prices[symbol] = None
                        
                except Exception as e:
                    print(f"   ❌ {symbol} 조회 실패: {e}")
                    prices[symbol] = None
                
                time.sleep(0.5)  # API 부하 방지
            
            self.price_cache = prices
            self.last_price_update = datetime.now()
            print(f"✅ 가격 조회 완료: {len([p for p in prices.values() if p])}개 성공\n")
            
            return prices
            
        except Exception as e:
            print(f"❌ 가격 조회 실패: {e}")
            return {}
    
    def predict_signal(self, symbol):
        """
        단일 종목에 대한 예측 수행 (실제 가격 사용)
        
        Args:
            symbol: 종목 심볼 (예: 'BTC')
            
        Returns:
            dict: 예측 결과
        """
        try:
            # 1. 가격 가져오기
            price = self.price_cache.get(symbol)
            if price is None:
                print(f"   ❌ {symbol}: 가격 정보 없음")
                return None
            
            # 2. 랜덤 시그널 생성 (테스트용)
            signal_type = random.choice(self.signal_types)
            
            # 3. 신뢰도 (0.6 ~ 0.95)
            confidence = round(random.uniform(0.60, 0.95), 4)
            prediction_probability = round(random.uniform(0.55, 0.92), 4)
            
            # 4. 가짜 특성 데이터 (실제로는 모델에서 계산)
            features = {
                'rsi': round(random.uniform(30, 70), 2),
                'macd': round(random.uniform(-100, 100), 2),
                'bb_position': round(random.uniform(0, 1), 2),
                'volume_ratio': round(random.uniform(0.5, 2.0), 2),
                'volatility': round(random.uniform(0.01, 0.05), 4)
            }
            
            # 5. 바이낸스 심볼로 변환
            binance_symbol = self.binance_symbols[symbol]
            
            result = {
                'symbol': binance_symbol,
                'signal_type': signal_type,
                'confidence': confidence,
                'prediction_probability': prediction_probability,
                'price': price,
                'features': features,
                'timestamp': datetime.now()
            }
            
            emoji = '🟢' if signal_type == 'LONG' else '🔴' if signal_type == 'SHORT' else '⚪'
            print(f"   {emoji} {symbol:6s} -> {signal_type:5s} (신뢰도: {confidence:.2%}, 가격: ${price:,.4f})")
            
            return result
            
        except Exception as e:
            print(f"   ❌ {symbol} 예측 실패: {e}")
            return None
    
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
            cursor = conn.cursor(buffered=True)
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
            cursor.fetchall()  # 남은 결과 모두 읽기
            
            if existing:
                # UPDATE
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
                    f"Test: Updated at {signal_data['timestamp'].strftime('%H:%M:%S')}",
                    signal_data['timestamp'],
                    existing[0]
                )
                cursor.execute(update_query, values)
                action = "업데이트"
            else:
                # INSERT
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
                    'test_v1.0',
                    f"Test: Created at {signal_data['timestamp'].strftime('%H:%M:%S')}",
                    signal_data['timestamp'],
                    False
                )
                cursor.execute(insert_query, values)
                action = "신규 생성"
            
            conn.commit()
            print(f"   → DB {action}: {signal_data['symbol']}")
            return True
            
        except Exception as e:
            print(f"   → DB 저장 실패: {e}")
            conn.rollback()
            return False
            
        finally:
            cursor.close()
            conn.close()
    
    def run_prediction_cycle(self):
        """
        모든 종목에 대한 예측 사이클 실행
        """
        print("\n" + "="*70)
        print(f"🔄 예측 사이클 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # 가격 갱신
        self.fetch_real_prices()
        
        success_count = 0
        fail_count = 0
        
        # 모든 종목 순회
        for symbol in self.symbols.keys():
            try:
                # 1. 시그널 예측
                signal_data = self.predict_signal(symbol)
                
                # 2. DB 저장
                if signal_data:
                    if self.save_to_database(signal_data):
                        success_count += 1
                    else:
                        fail_count += 1
                else:
                    fail_count += 1
                    
                time.sleep(0.5)
                
            except Exception as e:
                print(f"{symbol} 처리 중 오류: {e}")
                fail_count += 1
        
        print("\n" + "="*70)
        print(f"✅ 예측 사이클 완료: 성공 {success_count}개, 실패 {fail_count}개")
        print("="*70 + "\n")
        
        return success_count, fail_count
    
    def start_test_scheduler(self, interval_seconds=40):
        """
        테스트 스케줄러 시작 (10초마다 실행)
        
        Args:
            interval_seconds: 실행 간격 (초, 기본값 10초)
        """
        print(f"\n{'='*70}")
        print(f"🧪 테스트 스케줄러 시작")
        print(f"{'='*70}")
        print(f"⏱️  실행 간격: {interval_seconds}초마다")
        print(f"📊 감시 종목: {len(self.symbols)}개")
        print(f"💰 실제 가격 사용 (야후 파이낸스)")
        print(f"{'='*70}")
        print("📌 Ctrl+C를 눌러 테스트를 중단할 수 있습니다.\n")
        
        cycle_count = 0
        total_success = 0
        total_fail = 0
        
        try:
            # 즉시 1회 실행
            print("🚀 초기 예측 사이클 실행...\n")
            success, fail = self.run_prediction_cycle()
            cycle_count += 1
            total_success += success
            total_fail += fail
            
            # 정기 실행
            while True:
                print(f"⏳ {interval_seconds}초 대기 중... (다음 사이클: {cycle_count + 1})")
                time.sleep(interval_seconds)
                
                success, fail = self.run_prediction_cycle()
                cycle_count += 1
                total_success += success
                total_fail += fail
                
                print(f"📊 누적 통계: {cycle_count}사이클, 성공 {total_success}개, 실패 {total_fail}개\n")
                
        except KeyboardInterrupt:
            print(f"\n\n{'='*70}")
            print(f"🛑 테스트 중단됨")
            print(f"{'='*70}")
            print(f"📊 최종 통계:")
            print(f"   - 총 사이클: {cycle_count}회")
            print(f"   - 총 성공: {total_success}개")
            print(f"   - 총 실패: {total_fail}개")
            print(f"   - 성공률: {(total_success/(total_success+total_fail)*100):.1f}%" if (total_success+total_fail) > 0 else "   - 성공률: N/A")
            print(f"{'='*70}\n")
    
    def test_single_cycle(self):
        """단일 사이클 테스트 (1회만 실행)"""
        print("\n🧪 단일 사이클 테스트 실행\n")
        self.run_prediction_cycle()
    
    def clear_test_signals(self):
        """테스트 시그널 삭제 (model_version='test_v1.0')"""
        conn = self.connect_db()
        if conn is None:
            return
        
        try:
            cursor = conn.cursor()
            
            delete_query = """
            DELETE FROM trading_signals
            WHERE model_version = 'test_v1.0'
            """
            
            cursor.execute(delete_query)
            conn.commit()
            
            deleted_count = cursor.rowcount
            print(f"\n✅ 테스트 시그널 {deleted_count}개 삭제 완료\n")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"\n❌ 삭제 실패: {e}\n")
    
    def clear_today_signals(self):
        """오늘 날짜 시그널 전체 삭제"""
        conn = self.connect_db()
        if conn is None:
            return
        
        try:
            cursor = conn.cursor()
            today = datetime.now().date()
            
            delete_query = """
            DELETE FROM trading_signals
            WHERE DATE(created_at) = %s
            """
            
            cursor.execute(delete_query, (today,))
            conn.commit()
            
            deleted_count = cursor.rowcount
            print(f"\n✅ 오늘({today}) 시그널 {deleted_count}개 삭제 완료\n")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"\n❌ 삭제 실패: {e}\n")


def test_database_connection(db_config):
    """데이터베이스 연결 테스트"""
    print("\n🔍 데이터베이스 연결 테스트\n")
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        cursor.execute("SHOW TABLES LIKE 'trading_signals'")
        if not cursor.fetchone():
            print("❌ 'trading_signals' 테이블이 없습니다.")
            print("   trading_signals.sql 파일을 먼저 실행해주세요.")
            cursor.close()
            conn.close()
            return False
        
        print("✅ 데이터베이스 연결 성공!")
        print(f"✅ 'trading_signals' 테이블 확인 완료")
        
        cursor.execute("SELECT COUNT(*) FROM trading_signals")
        count = cursor.fetchone()[0]
        print(f"\n📊 현재 저장된 시그널: {count}개")
        
        cursor.execute("SELECT COUNT(*) FROM trading_signals WHERE model_version = 'test_v1.0'")
        test_count = cursor.fetchone()[0]
        if test_count > 0:
            print(f"🧪 테스트 시그널: {test_count}개 (삭제 가능)")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        return False


def test_yahoo_finance(test_system):
    """야후 파이낸스 API 테스트"""
    print("\n🧪 야후 파이낸스 API 테스트\n")
    
    for symbol, ticker in test_system.symbols.items():
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period='1d')
            
            if not data.empty:
                price = float(data['Close'].iloc[-1])
                if symbol == 'SHIB':
                    price = price * 1000  # 1000SHIB 변환
                
                binance_symbol = test_system.binance_symbols[symbol]
                print(f"✅ {symbol:6s} ({binance_symbol:15s}): ${price:>15,.6f}")
            else:
                print(f"❌ {symbol}: 데이터 없음")
                
        except Exception as e:
            print(f"❌ {symbol} 조회 실패: {e}")
        
        time.sleep(0.5)
    
    print("\n✅ API 테스트 완료\n")


def main():
    """메인 함수"""
    
    db_config = {
        'host': 'localhost',
        'database': 'trading_signals',
        'user': 'root',
        'password': 'ghkd2759A!'
    }
    
    print("\n" + "="*70)
    print("🧪 AI Trading Signal Test System")
    print("   (11개 주요 종목 감시: BTC, ETH, SHIB, DOT, BCH, AVAX,")
    # print("   (3개 주요 종목 감시: ETH, SHIB, ADA)")  # 🔥 수정
    print("    LINK, ADA, AAVE, TAO, SEI)")
    print("="*70)
    
    # DB 연결 테스트
    if not test_database_connection(db_config):
        print("\n❌ 데이터베이스 연결에 실패했습니다.")
        return
    
    # 테스트 시스템 초기화
    test_system = AutoTradingSignalTest(db_config)
    
    # 사용자 선택
    print("\n" + "="*70)
    print("📌 옵션을 선택하세요:")
    print("="*70)
    print("1. 자동 테스트 시작 (10초마다 11개 종목 시그널 생성)")
    print("2. 단일 사이클 테스트 (11개 종목 1회만 실행)")
    print("3. 테스트 시그널 삭제 (model_version='test_v1.0')")
    print("4. 오늘 날짜 시그널 전체 삭제")
    print("5. 야후 파이낸스 API 테스트")
    print("0. 종료")
    print("="*70)
    
    choice = input("\n선택 (0-5): ").strip()
    
    if choice == '1':
        test_system.start_test_scheduler(interval_seconds=15)
        
    elif choice == '2':
        test_system.test_single_cycle()
        
    elif choice == '3':
        confirm = input("\n⚠️  정말 테스트 시그널을 전체 삭제하시겠습니까? (y/n): ").strip().lower()
        if confirm == 'y':
            test_system.clear_test_signals()
        else:
            print("❌ 취소되었습니다.")
    
    elif choice == '4':
        today = datetime.now().strftime('%Y-%m-%d')
        confirm = input(f"\n⚠️  정말 오늘({today}) 날짜의 모든 시그널을 삭제하시겠습니까? (y/n): ").strip().lower()
        if confirm == 'y':
            test_system.clear_today_signals()
        else:
            print("❌ 취소되었습니다.")
            
    elif choice == '5':
        test_yahoo_finance(test_system)
        
    elif choice == '0':
        print("\n👋 프로그램을 종료합니다.")
    
    else:
        print("\n❌ 잘못된 선택입니다.")


if __name__ == "__main__":
    main()