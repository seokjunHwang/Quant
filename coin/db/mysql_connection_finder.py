import mysql.connector
from mysql.connector import Error
import getpass

def find_mysql_connection():
    """MySQL 연결 정보를 찾기 위한 자동 테스트"""
    
    print("🔍 MySQL 연결 정보 탐지 시작")
    print("=" * 50)
    
    # 일반적인 포트들 시도
    common_ports = [3306, 3307, 3308]
    
    # 사용자 정보 입력
    print("MySQL 정보를 입력해주세요:")
    username = input("Username (기본값: root): ").strip() or 'root'
    
    # 비밀번호 입력 (숨김 처리)
    password = getpass.getpass("Password: ")
    
    successful_configs = []
    
    # 각 포트별로 연결 시도
    for port in common_ports:
        print(f"\n🔍 포트 {port} 연결 시도...")
        
        config = {
            'host': 'localhost',
            'port': port,
            'user': username,
            'password': password
        }
        
        try:
            # 데이터베이스 없이 연결 시도 (서버 연결만 확인)
            connection = mysql.connector.connect(**config)
            
            if connection.is_connected():
                cursor = connection.cursor()
                
                # MySQL 버전 확인
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()[0]
                
                # 데이터베이스 목록 확인
                cursor.execute("SHOW DATABASES")
                databases = [db[0] for db in cursor.fetchall()]
                
                print(f"✅ 포트 {port} 연결 성공!")
                print(f"   MySQL 버전: {version}")
                print(f"   데이터베이스: {databases}")
                
                # trading_signals 데이터베이스가 있는지 확인
                if 'trading_signals' in databases:
                    print(f"   ✅ 'trading_signals' 데이터베이스 발견!")
                    config['database'] = 'trading_signals'
                else:
                    print(f"   ⚠️  'trading_signals' 데이터베이스 없음")
                
                successful_configs.append(config.copy())
                
                cursor.close()
                connection.close()
                
        except Error as e:
            print(f"   ❌ 포트 {port} 연결 실패: {e}")
    
    # 성공한 연결이 있는 경우
    if successful_configs:
        print(f"\n🎉 {len(successful_configs)}개의 성공적인 연결을 찾았습니다!")
        
        # 가장 적합한 설정 선택 (trading_signals DB가 있는 것 우선)
        best_config = None
        for config in successful_configs:
            if 'database' in config:
                best_config = config
                break
        
        if not best_config:
            best_config = successful_configs[0]
        
        print(f"\n💾 추천 설정:")
        print("-" * 30)
        for key, value in best_config.items():
            if key == 'password':
                print(f"  {key}: {'*' * len(value)}")
            else:
                print(f"  {key}: {value}")
        
        # 설정 파일 생성
        create_config_file(best_config)
        
        # 연결 테스트
        if 'database' in best_config:
            test_trading_signals_connection(best_config)
        
        return best_config
    
    else:
        print("\n❌ 모든 연결 시도 실패")
        print("\n💡 해결 방법:")
        print("1. MySQL Workbench에서 연결 정보 다시 확인")
        print("2. MySQL 서비스가 실행 중인지 확인")
        print("3. Windows 서비스에서 'MySQL80' 상태 확인")
        return None

def create_config_file(config):
    """설정 파일 생성"""
    config_content = f"""# MySQL 연결 설정
DB_CONFIG = {{
    'host': '{config['host']}',
    'port': {config['port']},
    'user': '{config['user']}',
    'password': '{config['password']}'"""
    
    if 'database' in config:
        config_content += f",\n    'database': '{config['database']}'"
    
    config_content += "\n}\n"
    
    # 파일 저장
    with open('db_config.py', 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print(f"\n📁 설정이 'db_config.py' 파일에 저장되었습니다!")

def test_trading_signals_connection(config):
    """trading_signals 데이터베이스 연결 테스트"""
    try:
        print(f"\n🧪 trading_signals 데이터베이스 테스트...")
        
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor(dictionary=True)
        
        # 테이블 목록 확인
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        table_names = [list(table.values())[0] for table in tables]
        
        print(f"✅ 테이블 {len(table_names)}개 발견: {table_names}")
        
        # 각 테이블의 레코드 수 확인
        for table_name in table_names:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            count = cursor.fetchone()['count']
            print(f"   {table_name}: {count}개 레코드")
        
        cursor.close()
        connection.close()
        
    except Error as e:
        print(f"❌ 데이터베이스 테스트 실패: {e}")

if __name__ == "__main__":
    # MySQL 연결 정보 찾기
    config = find_mysql_connection()
    
    if config:
        print(f"\n🚀 다음 단계:")
        print("1. 생성된 'db_config.py' 파일 확인")
        print("2. 다른 스크립트에서 이 설정 사용")
        print("3. 웹훅 서버 설정 진행")
    else:
        print(f"\n🔧 추가 확인 사항:")
        print("1. MySQL Workbench에서 Test Connection 시도")
        print("2. Windows 서비스 관리자에서 MySQL80 서비스 확인")
        print("3. 방화벽 설정 확인")