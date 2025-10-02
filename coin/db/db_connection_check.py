import mysql.connector
from mysql.connector import Error
import json
from datetime import datetime

pw = 'ghkd2759A!'
def test_database_connection():
    """데이터베이스 연결 및 테이블 확인"""
    
    # MySQL 연결 설정 (본인의 비밀번호로 수정)
    db_config = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': pw,  # ⭐ 여기에 실제 비밀번호 입력
        'database': 'trading_signals'
    }
    
    try:
        # 1. 데이터베이스 연결
        print("=" * 50)
        print("🔍 데이터베이스 연결 테스트 시작")
        print("=" * 50)
        
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        
        print("✅ MySQL 연결 성공!")
        
        # 2. 테이블 목록 확인
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        print(f"\n📋 생성된 테이블 목록: {len(tables)}개")
        print("-" * 30)
        for table in tables:
            table_name = list(table.values())[0]
            print(f"  📄 {table_name}")
        
        # 3. 각 테이블의 레코드 수 확인
        print(f"\n📊 테이블별 데이터 현황:")
        print("-" * 30)
        
        table_names = [list(table.values())[0] for table in tables]
        for table_name in table_names:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            count = cursor.fetchone()['count']
            print(f"  {table_name:<25} : {count:>3}개")
        
        # 4. trading_signals 테이블 구조 확인
        print(f"\n🏗️  trading_signals 테이블 구조:")
        print("-" * 50)
        cursor.execute("DESCRIBE trading_signals")
        columns = cursor.fetchall()
        
        for col in columns:
            print(f"  {col['Field']:<20} {col['Type']:<25} {col['Null']:<8}")
        
        # 5. 샘플 데이터 확인
        cursor.execute("SELECT * FROM trading_signals LIMIT 3")
        sample_data = cursor.fetchall()
        
        if sample_data:
            print(f"\n📄 샘플 데이터:")
            print("-" * 50)
            for i, record in enumerate(sample_data, 1):
                print(f"  레코드 {i}:")
                print(f"    ID: {record['id']}")
                print(f"    전략: {record['strategy_name']}")
                print(f"    심볼: {record['symbol']}")
                print(f"    시그널: {record['signal_type']}")
                print(f"    생성시간: {record['created_at']}")
                print()
        
        # 6. 전략 설정 확인
        cursor.execute("SELECT strategy_name, strategy_type, is_active FROM strategy_configs")
        strategies = cursor.fetchall()
        
        print(f"⚙️  등록된 전략: {len(strategies)}개")
        print("-" * 30)
        for strategy in strategies:
            status = "🟢" if strategy['is_active'] else "🔴"
            print(f"  {status} {strategy['strategy_name']:<25} ({strategy['strategy_type']})")
        
        # 7. 지원 심볼 확인
        cursor.execute("SELECT symbol, base_asset, quote_asset, is_active FROM supported_symbols")
        symbols = cursor.fetchall()
        
        print(f"\n💰 지원 심볼: {len(symbols)}개")
        print("-" * 30)
        for symbol in symbols:
            status = "🟢" if symbol['is_active'] else "🔴"
            print(f"  {status} {symbol['symbol']:<12} ({symbol['base_asset']}/{symbol['quote_asset']})")
        
        print("\n🎉 데이터베이스 설정이 완료되었습니다!")
        
        cursor.close()
        connection.close()
        
        return True
        
    except Error as e:
        print(f"❌ 데이터베이스 오류: {e}")
        return False

def add_test_signal():
    """테스트용 시그널 추가"""
    
    db_config = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': pw,  # ⭐ 여기에 실제 비밀번호 입력
        'database': 'trading_signals'
    }
    
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        
        # 테스트 시그널 추가
        test_signals = [
            ('RSI_REVERSAL', 'BTCUSDT', '1h', 'LONG', 'TRADINGVIEW', 45000.50, 0.85, '테스트 롱 시그널'),
            ('XGBOOST_PREDICTOR', 'ETHUSDT', '1d', 'SHORT', 'AI_MODEL', 2800.75, 0.72, 'AI 숏 예측'),
            ('MACD_MOMENTUM', 'ADAUSDT', '4h', 'HOLD', 'TRADINGVIEW', 1.25, 0.45, '관망 신호')
        ]
        
        query = """
        INSERT INTO trading_signals 
        (strategy_name, symbol, timeframe, signal_type, signal_source, price, confidence, message)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.executemany(query, test_signals)
        connection.commit()
        
        print(f"✅ {len(test_signals)}개의 테스트 시그널이 추가되었습니다!")
        
        cursor.close()
        connection.close()
        
    except Error as e:
        print(f"❌ 테스트 시그널 추가 실패: {e}")

if __name__ == "__main__":
    # 1단계: 연결 테스트
    success = test_database_connection()
    
    if success:
        print("\n" + "=" * 50)
        print("🧪 테스트 시그널 추가")
        print("=" * 50)
        
        # 2단계: 테스트 데이터 추가
        add_test_signal()
        
        print("\n💡 다음 단계:")
        print("1. 웹훅 서버 설정")
        print("2. AI 모델 연동")
        print("3. 기존 PyQt5 GUI 연동")
        
    else:
        print("\n🔧 문제 해결 필요:")
        print("1. MySQL 서비스 실행 확인")
        print("2. 비밀번호 확인") 
        print("3. 데이터베이스 이름 확인")