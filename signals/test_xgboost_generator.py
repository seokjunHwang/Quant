# XGBoost 테스트용 시그널 생성기
import mysql.connector
from mysql.connector import Error
import asyncio
import aiohttp
import random
import time
from datetime import datetime
from typing import Optional, Tuple

# 데이터베이스 설정
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'ghkd2759A!',  # 실제 비밀번호로 변경
    'database': 'trading_signals'
}

class XGBoostTestGenerator:
    def __init__(self):
        """XGBoost 테스트 시그널 생성기 초기화"""
        self.symbol = 'BTCUSDT'
        self.timeframe = '1h'
        self.strategy_name = 'AI_XGBOOST_PREDICTOR'
        
        # 포지션 상태 추적 (중복 방지용)
        self.current_position = None  # None, 'LONG', 'SHORT'
        self.last_signal_time = None
        self.min_signal_interval = 30  # 최소 30초 간격
        
    async def get_current_price(self) -> float:
        """바이낸스에서 BTCUSDT 현재가 가져오기"""
        try:
            url = "https://api.binance.com/api/v3/ticker/price"
            params = {'symbol': self.symbol}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    price = float(data['price'])
                    print(f"💰 {self.symbol} 현재가: ${price:,.2f}")
                    return price
                    
        except Exception as e:
            print(f"❌ 가격 조회 실패: {e}")
            # 오류 시 더미 가격 반환
            return 45000.0 + random.uniform(-2000, 2000)
    
    def get_current_position(self) -> Optional[str]:
        """현재 포지션 상태 확인"""
        try:
            connection = mysql.connector.connect(**DB_CONFIG)
            cursor = connection.cursor(dictionary=True)
            
            # 최근 24시간 내 마지막 시그널 확인
            query = """
            SELECT signal_type FROM trading_signals 
            WHERE strategy_name = %s 
            AND symbol = %s 
            AND signal_type IN ('LONG', 'SHORT')
            AND created_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)
            ORDER BY created_at DESC 
            LIMIT 1
            """
            
            cursor.execute(query, (self.strategy_name, self.symbol))
            result = cursor.fetchone()
            
            cursor.close()
            connection.close()
            
            if result:
                position = result['signal_type']
                print(f"📊 현재 포지션: {position}")
                return position
            else:
                print("📊 현재 포지션: 없음")
                return None
                
        except Exception as e:
            print(f"❌ 포지션 확인 실패: {e}")
            return None
    
    def generate_smart_signal(self) -> Tuple[str, float, str]:
        """중복 방지 스마트 시그널 생성"""
        current_position = self.get_current_position()
        
        # 시그널 선택 로직
        available_signals = []
        
        if current_position is None:
            # 포지션 없음: LONG, SHORT 모두 가능
            available_signals = ['LONG', 'SHORT', 'HOLD']
            weights = [0.4, 0.35, 0.25]
        elif current_position == 'LONG':
            # 롱 포지션: SHORT(청산+숏), HOLD만 가능
            available_signals = ['SHORT', 'HOLD']
            weights = [0.6, 0.4]  # 청산 확률 높게
        elif current_position == 'SHORT':
            # 숏 포지션: LONG(청산+롱), HOLD만 가능  
            available_signals = ['LONG', 'HOLD']
            weights = [0.6, 0.4]  # 청산 확률 높게
        else:
            # 기본값
            available_signals = ['HOLD']
            weights = [1.0]
        
        # 랜덤 시그널 선택
        signal_type = random.choices(available_signals, weights=weights)[0]
        confidence = random.uniform(0.65, 0.90)
        
        # 메시지 생성
        if current_position and signal_type != 'HOLD' and signal_type != current_position:
            message = f'XGBoost AI: {current_position} 청산 후 {signal_type} 진입 추천'
        elif signal_type == 'HOLD':
            message = f'XGBoost AI: 관망 (현재 포지션: {current_position or "없음"})'
        else:
            message = f'XGBoost AI: {signal_type} 진입 추천'
        
        return signal_type, confidence, message
    
    def save_signal_to_db(self, signal_type: str, confidence: float, price: float, message: str) -> bool:
        """시그널을 데이터베이스에 저장"""
        try:
            connection = mysql.connector.connect(**DB_CONFIG)
            cursor = connection.cursor()
            
            query = """
            INSERT INTO trading_signals 
            (strategy_name, symbol, timeframe, signal_type, signal_source, 
             price, confidence, message, created_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (
                self.strategy_name,
                self.symbol,
                self.timeframe,
                signal_type,
                'AI_MODEL',
                price,
                confidence,
                message,
                datetime.now()
            )
            
            cursor.execute(query, values)
            connection.commit()
            
            cursor.close()
            connection.close()
            
            return True
            
        except Error as e:
            print(f"❌ DB 저장 실패: {e}")
            return False
    
    async def generate_test_signal(self):
        """테스트용 시그널 생성"""
        try:
            print(f"🤖 XGBoost 시그널 생성 중...")
            
            # 1. 현재 가격 가져오기
            current_price = await self.get_current_price()
            
            # 2. 스마트 시그널 생성 (중복 방지)
            signal_type, confidence, message = self.generate_smart_signal()
            
            # 3. 데이터베이스에 저장
            success = self.save_signal_to_db(
                signal_type=signal_type,
                confidence=confidence,
                price=current_price,
                message=message
            )
            
            if success:
                # 이모지와 색상으로 시그널 타입 표시
                signal_emoji = {
                    'LONG': '🟢',
                    'SHORT': '🔴', 
                    'HOLD': '🟡'
                }
                
                emoji = signal_emoji.get(signal_type, '⚪')
                print(f"{emoji} XGBoost 시그널: {signal_type} (신뢰도: {confidence:.1%})")
                print(f"   가격: ${current_price:,.2f}")
                print(f"   메시지: {message}")
                
                # 포지션 상태 업데이트
                if signal_type in ['LONG', 'SHORT']:
                    self.current_position = signal_type
                
                return True
            else:
                print("❌ 시그널 저장 실패")
                return False
                
        except Exception as e:
            print(f"❌ 시그널 생성 실패: {e}")
            return False
    
    async def run_test_generation(self, interval_seconds: int = 10):
        """테스트용 시그널 생성 실행"""
        print("🚀 XGBoost 테스트 시그널 생성기 시작")
        print("=" * 60)
        print(f"📊 테스트 심볼: {self.symbol}")
        print(f"⏰ 생성 주기: {interval_seconds}초")
        print(f"🤖 전략: {self.strategy_name}")
        print(f"📈 시간대: {self.timeframe}")
        print(f"🧠 중복 방지: 활성화")
        print("=" * 60)
        
        cycle_count = 1
        
        while True:
            try:
                start_time = datetime.now()
                print(f"\n🔄 [{start_time.strftime('%H:%M:%S')}] 사이클 {cycle_count}")
                
                # 시그널 생성
                success = await self.generate_test_signal()
                
                if success:
                    print(f"✅ 시그널 생성 완료")
                else:
                    print(f"⚠️ 시그널 생성 실패")
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                print(f"⏱️ 소요시간: {duration:.1f}초")
                print(f"⏳ 다음 실행까지 {interval_seconds}초 대기...")
                
                cycle_count += 1
                
                # 지정된 시간만큼 대기
                await asyncio.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                print("\n🛑 XGBoost 시그널 생성기 중지됨")
                break
            except Exception as e:
                print(f"❌ 시그널 생성 중 오류: {e}")
                await asyncio.sleep(5)  # 5초 대기 후 재시도
    
    def test_database_connection(self) -> bool:
        """데이터베이스 연결 테스트"""
        try:
            connection = mysql.connector.connect(**DB_CONFIG)
            cursor = connection.cursor()
            
            # 테이블 존재 확인
            cursor.execute("SHOW TABLES LIKE 'trading_signals'")
            result = cursor.fetchone()
            
            if result:
                # 기존 시그널 수 확인
                cursor.execute("SELECT COUNT(*) FROM trading_signals WHERE strategy_name = %s", (self.strategy_name,))
                count = cursor.fetchone()[0]
                print(f"✅ 데이터베이스 연결 성공!")
                print(f"📊 기존 {self.strategy_name} 시그널: {count}개")
                return True
            else:
                print("❌ trading_signals 테이블이 존재하지 않습니다.")
                return False
                
        except Error as e:
            print(f"❌ 데이터베이스 연결 실패: {e}")
            return False
        finally:
            if 'connection' in locals() and connection.is_connected():
                cursor.close()
                connection.close()

# 메인 실행 함수
async def main():
    """메인 실행 함수"""
    print("🧪 XGBoost 테스트 시그널 생성기")
    print("=" * 40)
    
    # 시그널 생성기 초기화
    generator = XGBoostTestGenerator()
    
    # 데이터베이스 연결 테스트
    if not generator.test_database_connection():
        print("❌ 데이터베이스 연결에 실패했습니다. 프로그램을 종료합니다.")
        return
    
    print("\n💡 테스트 특징:")
    print("   - BTCUSDT만 거래")
    print("   - 1시간 타임프레임")
    print("   - 실제 바이낸스 현재가 사용")
    print("   - 중복 포지션 방지 (롱 → 롱 X)")
    print("   - 10초마다 시그널 생성")
    
    try:
        # 시그널 생성 시작 (10초 간격)
        await generator.run_test_generation(interval_seconds=10)
    except KeyboardInterrupt:
        print("\n👋 테스트 종료")

if __name__ == "__main__":
    # 이벤트 루프 실행
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n프로그램이 중단되었습니다.")