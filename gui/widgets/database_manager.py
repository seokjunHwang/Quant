# database_manager.py - 거래 기록을 위한 데이터베이스 관리자

import mysql.connector
from mysql.connector import Error
from datetime import datetime


class DatabaseManager:
    def __init__(self, db_config):
        """
        데이터베이스 매니저 초기화
        
        Args:
            db_config: MySQL 연결 설정 딕셔너리
                {
                    'host': 'localhost',
                    'database': 'trading_signals',
                    'user': 'root',
                    'password': 'your_password'
                }
        """
        self.db_config = db_config

    def get_connection(self):
        """데이터베이스 연결을 생성하고 반환합니다."""
        try:
            connection = mysql.connector.connect(**self.db_config)
            print(f"✅ DB 연결 성공: {self.db_config['database']}")
            return connection
        except Error as e:
            print(f"❌ DB 연결 오류: {e}")
            return None

    def save_trade(self, trade_data):
        """
        체결된 거래 내역을 trade_history 테이블에 저장합니다.
        
        Args:
            trade_data: 거래 데이터 딕셔너리
                {
                    'order_id': '주문ID',
                    'symbol': '심볼',
                    'side': 'LONG' or 'SHORT',
                    'trade_type': 'ENTRY' or 'EXIT',
                    'quantity': 수량,
                    'price': 가격,
                    'realized_pnl': 실현손익 (선택),
                    'commission': 수수료 (선택),
                    'trade_time': datetime 객체
                }
        
        Returns:
            bool: 저장 성공 여부
        """
        connection = self.get_connection()
        if not connection:
            print("❌ DB 연결 실패로 거래 저장 불가")
            return False

        query = """
        INSERT INTO trade_history
        (order_id, symbol, side, trade_type, quantity, price, leverage, realized_pnl, commission, trade_time)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            cursor = connection.cursor()
            
            # 디버깅용 데이터 출력
            print(f"\n{'='*70}\n📝 DB 저장 데이터:")
            print(f"   - 주문ID: {trade_data.get('order_id')}, 심볼: {trade_data.get('symbol')}, 방향: {trade_data.get('side')}")
            print(f"   - 수량: {trade_data.get('quantity')}, 가격: {trade_data.get('price')}, 레버리지: {trade_data.get('leverage')}")
            print(f"   - 손익: {trade_data.get('realized_pnl', 0.0)}, 수수료: {trade_data.get('commission', 0.0)}")
            print(f"{'='*70}\n")
            
            # ▼▼▼ [수정] 쿼리에 leverage 값 추가 ▼▼▼
            cursor.execute(query, (
                trade_data.get('order_id'),
                trade_data.get('symbol'),
                trade_data.get('side'),
                trade_data.get('trade_type'),
                trade_data.get('quantity'),
                trade_data.get('price'),
                trade_data.get('leverage', 1), # 레버리지 값 추가
                trade_data.get('realized_pnl', 0.0),
                trade_data.get('commission', 0.0),
                trade_data.get('trade_time')
            ))
            connection.commit()
            
            # 🔥 저장 확인
            rows_affected = cursor.rowcount
            print(f"✅ DB에 거래 기록 저장 완료: {trade_data['symbol']} {trade_data['side']} {trade_data['trade_type']} (영향받은 행: {rows_affected})")
            
            cursor.close()
            connection.close()
            return True
            
        except Error as e:
            print(f"❌ DB 거래 기록 저장 실패: {e}")
            print(f"   에러 코드: {e.errno if hasattr(e, 'errno') else 'N/A'}")
            print(f"   에러 메시지: {e.msg if hasattr(e, 'msg') else str(e)}")
            connection.rollback()
            cursor.close()
            connection.close()
            return False
    
    def get_trade_history(self, symbol=None, start_date=None, end_date=None, limit=100):
        """
        거래 내역 조회
        
        Args:
            symbol: 심볼 필터 (선택)
            start_date: 시작 날짜 (선택)
            end_date: 종료 날짜 (선택)
            limit: 최대 조회 개수
        
        Returns:
            list: 거래 내역 리스트
        """
        connection = self.get_connection()
        if not connection:
            return []
        
        try:
            cursor = connection.cursor(dictionary=True)
            
            query = "SELECT * FROM trade_history WHERE 1=1"
            params = []
            
            if symbol:
                query += " AND symbol = %s"
                params.append(symbol)
            
            if start_date:
                query += " AND trade_time >= %s"
                params.append(start_date)
            
            if end_date:
                query += " AND trade_time <= %s"
                params.append(end_date)
            
            query += " ORDER BY trade_time DESC LIMIT %s"
            params.append(limit)
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            cursor.close()
            connection.close()
            
            return results
            
        except Error as e:
            print(f"❌ 거래 내역 조회 실패: {e}")
            return []
    
    def get_statistics(self, start_date=None, end_date=None):
        """
        거래 통계 조회
        
        Returns:
            dict: 통계 정보
        """
        connection = self.get_connection()
        if not connection:
            return None
        
        try:
            cursor = connection.cursor(dictionary=True)
            
            query = """
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN side = 'LONG' THEN 1 ELSE 0 END) as long_trades,
                SUM(CASE WHEN side = 'SHORT' THEN 1 ELSE0 END) as short_trades,
                SUM(CASE WHEN trade_type = 'ENTRY' THEN 1 ELSE 0 END) as entries,
                SUM(CASE WHEN trade_type = 'EXIT' THEN 1 ELSE 0 END) as exits,
                SUM(realized_pnl) as total_pnl,
                SUM(commission) as total_commission,
                AVG(realized_pnl) as avg_pnl,
                MAX(realized_pnl) as max_profit,
                MIN(realized_pnl) as max_loss
            FROM trade_history
            WHERE 1=1
            """
            params = []
            
            if start_date:
                query += " AND trade_time >= %s"
                params.append(start_date)
            
            if end_date:
                query += " AND trade_time <= %s"
                params.append(end_date)
            
            cursor.execute(query, params)
            stats = cursor.fetchone()
            
            cursor.close()
            connection.close()
            
            return stats
            
        except Error as e:
            print(f"❌ 통계 조회 실패: {e}")
            return None
    
    def test_connection(self):
        """
        데이터베이스 연결 및 테이블 확인
        
        Returns:
            bool: 연결 성공 여부
        """
        print("\n" + "="*70)
        print("🔍 DB 연결 테스트")
        print("="*70)
        
        try:
            # 1. 연결 테스트
            conn = self.get_connection()
            if not conn:
                return False
            
            cursor = conn.cursor()
            
            # 2. 테이블 존재 확인
            cursor.execute("SHOW TABLES LIKE 'trade_history'")
            table_exists = cursor.fetchone()
            
            if not table_exists:
                print("❌ 'trade_history' 테이블이 존재하지 않습니다.")
                print("   trading_signals.sql 파일을 실행하여 테이블을 생성하세요.")
                cursor.close()
                conn.close()
                return False
            
            print("✅ 'trade_history' 테이블 존재 확인")
            
            # 3. 테이블 구조 확인
            cursor.execute("DESCRIBE trade_history")
            columns = cursor.fetchall()
            print("\n📋 테이블 구조:")
            for col in columns:
                print(f"   - {col[0]}: {col[1]}")
            
            # 4. 레코드 수 확인
            cursor.execute("SELECT COUNT(*) FROM trade_history")
            count = cursor.fetchone()[0]
            print(f"\n📊 현재 저장된 거래 내역: {count}개")
            
            # 5. 최근 거래 확인
            cursor.execute("SELECT * FROM trade_history ORDER BY id DESC LIMIT 5")
            recent = cursor.fetchall()
            if recent:
                print("\n📝 최근 거래 내역:")
                for row in recent:
                    print(f"   - ID:{row[0]} {row[2]} {row[3]} {row[4]} 수량:{row[5]} 가격:{row[6]}")
            else:
                print("\n📝 아직 거래 내역이 없습니다.")
            
            cursor.close()
            conn.close()
            
            print("\n" + "="*70)
            print("✅ DB 테스트 완료 - 정상")
            print("="*70 + "\n")
            return True
            
        except Exception as e:
            print(f"\n❌ DB 테스트 실패: {e}")
            import traceback
            traceback.print_exc()
            print("="*70 + "\n")
            return False
    
    def clear_all_trades(self):
        """
        모든 거래 내역 삭제 (주의: 복구 불가)
        
        Returns:
            bool: 삭제 성공 여부
        """
        connection = self.get_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            
            # 삭제 전 개수 확인
            cursor.execute("SELECT COUNT(*) FROM trade_history")
            count = cursor.fetchone()[0]
            
            if count == 0:
                print("⚠️ 삭제할 거래 내역이 없습니다.")
                cursor.close()
                connection.close()
                return True
            
            print(f"⚠️ {count}개의 거래 내역을 삭제합니다...")
            
            # 전체 삭제
            cursor.execute("DELETE FROM trade_history")
            connection.commit()
            
            deleted = cursor.rowcount
            print(f"✅ {deleted}개의 거래 내역이 삭제되었습니다.")
            
            cursor.close()
            connection.close()
            return True
            
        except Error as e:
            print(f"❌ 거래 내역 삭제 실패: {e}")
            connection.rollback()
            cursor.close()
            connection.close()
            return False