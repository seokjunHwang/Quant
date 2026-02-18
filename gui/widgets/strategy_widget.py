# widgets/strategy_widget.py - 완전 수정 버전 (증거금 체크 + 심볼 검증 강화)
import sys
import asyncio
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
# from PyQt5.QtCore import pyqtSignal, QThread, Qt
# from PyQt5.QtWidgets import QDateEdit
# from PyQt5.QtCore import QDate
# from PyQt5.QtWidgets import *
# from PyQt5.QtCore import *
# from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

import json
import time
from decimal import Decimal, ROUND_DOWN
import csv
import os
from pathlib import Path



class DatabaseManager:
    def __init__(self, db_config):
        self.db_config = db_config
        # 🔥 수동 청산 기록 (심볼 저장)
        self.manually_closed_symbols = set()
        # 🔥 마지막 수동 청산 시간 기록
        self.manual_close_times = {}

    def clear_manual_close_records(self):
        """수동 청산 기록 초기화 (자동매매 시작 시 호출)"""
        self.manually_closed_symbols.clear()
        self.manual_close_times.clear()
        print("🧹 수동 청산 기록 초기화됨")     

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
        """체결된 거래 내역을 trade_history 테이블에 저장합니다."""
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
            
            print(f"\n{'='*70}")
            print(f"📝 DB 저장 시도")
            print(f"{'='*70}")
            print(f"   주문ID: {trade_data['order_id']}")
            print(f"   심볼: {trade_data['symbol']}")
            print(f"   방향: {trade_data['side']}")
            print(f"   타입: {trade_data['trade_type']}")
            print(f"   수량: {trade_data['quantity']}")
            print(f"   가격: {trade_data['price']}")
            print(f"   레버리지: {trade_data.get('leverage', 1)}")
            print(f"   손익: {trade_data.get('realized_pnl', 0.0)}")
            print(f"   수수료: {trade_data.get('commission', 0.0)}")
            print(f"   시간: {trade_data['trade_time']}")
            print(f"{'='*70}\n")
            
            cursor.execute(query, (
                trade_data['order_id'],
                trade_data['symbol'],
                trade_data['side'],
                trade_data['trade_type'],
                trade_data['quantity'],
                trade_data['price'],
                trade_data.get('leverage', 1),
                trade_data.get('realized_pnl', 0.0),
                trade_data.get('commission', 0.0),
                trade_data['trade_time']
            ))
            connection.commit()
            
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


class PositionManager:
    def __init__(self, client, max_positions=5):
        self.client = client
        self.max_positions = max_positions
        self.active_positions = {}
        
    async def get_current_positions(self):
        try:
            positions = await self.client.get_positions()
            self.active_positions = {}
            
            for pos in positions:
                symbol = pos.get('symbol', '')
                position_amt = float(pos.get('positionAmt', 0))
                
                if position_amt != 0:
                    self.active_positions[symbol] = {
                        'symbol': symbol,
                        'side': 'LONG' if position_amt > 0 else 'SHORT',
                        'quantity': abs(position_amt),
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'unrealized_pnl': float(pos.get('unRealizedProfit', 0)),
                        'leverage': float(pos.get('leverage', 1))
                    }
            
            return self.active_positions
            
        except Exception as e:
            print(f"❌ 포지션 조회 실패: {e}")
            return {}

    async def sync_positions_with_exchange(self):
        """
        🔥 거래소와 메모리 포지션 강제 동기화
        - 실제 거래소 포지션과 메모리 포지션을 비교하여 불일치 제거
        """
        try:
            print("\n🔄 포지션 동기화 시작...")
            
            # 거래소에서 실제 포지션 조회
            exchange_positions = await self.client.get_positions()
            
            # 실제로 존재하는 포지션만 추출 (position_amt != 0)
            actual_positions = {}
            for pos in exchange_positions:
                symbol = pos.get('symbol')
                position_amt = float(pos.get('positionAmt', 0))
                
                if position_amt != 0:
                    actual_positions[symbol] = {
                        'side': 'LONG' if position_amt > 0 else 'SHORT',
                        'quantity': abs(position_amt),
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'unrealized_pnl': float(pos.get('unRealizedProfit', 0)),
                        'leverage': int(pos.get('leverage', 1))
                    }
            
            # 메모리에만 있고 실제로는 없는 포지션 제거
            memory_only = set(self.active_positions.keys()) - set(actual_positions.keys())
            if memory_only:
                print(f"⚠️ 메모리에만 존재하는 포지션 제거: {memory_only}")
                for symbol in memory_only:
                    del self.active_positions[symbol]
            
            # 거래소에만 있고 메모리에 없는 포지션 추가
            exchange_only = set(actual_positions.keys()) - set(self.active_positions.keys())
            if exchange_only:
                print(f"ℹ️ 거래소에만 존재하는 포지션 추가: {exchange_only}")
                for symbol in exchange_only:
                    self.active_positions[symbol] = actual_positions[symbol]
            
            # 메모리 업데이트
            for symbol in actual_positions:
                self.active_positions[symbol] = actual_positions[symbol]
            
            print(f"✅ 동기화 완료: {len(self.active_positions)}개 포지션")
            
        except Exception as e:
            print(f"❌ 포지션 동기화 실패: {e}")
            import traceback
            traceback.print_exc()


# 바이낸스 심볼 정밀도 설정 (완전 보완된 버전)
# strategy_widget.py의 SYMBOL_PRECISION에 추가

# 매매 수량설정인데 그냥 바이낸스 API에서 심볼정보 가져와 캐싱하는걸로 대체
SYMBOL_PRECISION = {}
# SYMBOL_PRECISION = {
#     'BTCUSDT': {'price': 1, 'quantity': 3},
#     'ETHUSDT': {'price': 2, 'quantity': 3},
#     'BNBUSDT': {'price': 2, 'quantity': 2},
#     'ADAUSDT': {'price': 4, 'quantity': 0},
#     'DOGEUSDT': {'price': 5, 'quantity': 0},
#     'XRPUSDT': {'price': 4, 'quantity': 1},
#     'DOTUSDT': {'price': 3, 'quantity': 1},
#     'LINKUSDT': {'price': 3, 'quantity': 1},
#     'LTCUSDT': {'price': 2, 'quantity': 2},
#     'BCHUSDT': {'price': 2, 'quantity': 3},
#     'AVAXUSDT': {'price': 3, 'quantity': 1},
#     'SOLUSDT': {'price': 3, 'quantity': 1},
#     'MATICUSDT': {'price': 4, 'quantity': 0},
#     'ATOMUSDT': {'price': 3, 'quantity': 1},
#     'UNIUSDT': {'price': 3, 'quantity': 1},
#     '1000SHIBUSDT': {'price': 6, 'quantity': 0},
#     'TRXUSDT': {'price': 5, 'quantity': 0},
#     'PEPEUSDT': {'price': 7, 'quantity': 0},
#     '1000FLOKIUSDT': {'price': 5, 'quantity': 0},
#     'SANDUSDT': {'price': 4, 'quantity': 0},
#     'MANAUSDT': {'price': 4, 'quantity': 0},
#     'APTUSDT': {'price': 3, 'quantity': 1},
#     'OPUSDT': {'price': 4, 'quantity': 1},
#     'ARBUSDT': {'price': 4, 'quantity': 1},
#     'SUIUSDT': {'price': 4, 'quantity': 1},
#     'AAVEUSDT': {'price': 2, 'quantity': 2},
#     'TAOUSDT': {'price': 1, 'quantity': 3},
#     'SEIUSDT': {'price': 4, 'quantity': 0},
# }

# 바이낸스 API에서 심볼 정보를 가져와 캐싱하는 함수 추가
async def fetch_symbol_precision(client, symbol):
    """
    바이낸스 API에서 심볼 정밀도 조회 및 캐싱
    """
    global SYMBOL_PRECISION
    
    # 이미 캐싱된 경우 바로 반환
    if symbol in SYMBOL_PRECISION:
        print(f"         ✅ {symbol} 정밀도 캐시 사용: {SYMBOL_PRECISION[symbol]}")
        return SYMBOL_PRECISION[symbol]
    
    try:
        print(f"         📡 {symbol} API 조회 중...")
        symbol_info = await client.get_symbol_info(symbol)
        
        if symbol_info:
            price_precision = symbol_info.get('pricePrecision', 2)
            quantity_precision = symbol_info.get('quantityPrecision', 3)
            
            SYMBOL_PRECISION[symbol] = {
                'price': price_precision,
                'quantity': quantity_precision
            }
            
            print(f"✅ {symbol} 정밀도 로드 완료: 가격 {price_precision}자리, 수량 {quantity_precision}자리")
            return SYMBOL_PRECISION[symbol]
        else:
            print(f"⚠️ {symbol} API 응답 없음 - 기본값 사용")
            
    except Exception as e:
        print(f"❌ {symbol} 정밀도 조회 실패: {e}")
        import traceback
        traceback.print_exc()
    
    # 실패 시 기본값 반환 (캐싱하지 않음)
    default_precision = {'price': 2, 'quantity': 3}
    print(f"⚠️ {symbol} 기본 정밀도 사용: {default_precision}")
    return default_precision

# 바이낸스에 없는 심볼 매핑
SYMBOL_MAPPING = {
    'CROUSDT': None,
    'WETHUSDT': 'ETHUSDT',
    'STETHUSDT': 'ETHUSDT',
    'WBTCUSDT': 'BTCUSDT',
    'SHIBUSDT': '1000SHIBUSDT',
}

def adjust_quantity_precision(symbol, quantity):
    """
    심볼에 맞게 수량 정밀도 조정 + 최소값 보장
    
    ⚠️ 주의: SYMBOL_PRECISION에 해당 심볼이 없으면 기본값 사용
    사용 전에 fetch_symbol_precision()을 먼저 호출해야 함!
    """
    if symbol in SYMBOL_PRECISION:
        precision = SYMBOL_PRECISION[symbol]['quantity']
        adjusted = round(quantity, precision)
        
        # 최소값 보장
        min_val = 1 if precision == 0 else 10 ** (-precision)
        if adjusted < min_val:
            print(f"⚠️ {symbol}: 최소 수량 조정 {adjusted} -> {min_val}")
            adjusted = min_val
        
        print(f"   📏 {symbol} 수량 조정: {quantity:.8f} -> {adjusted} (정밀도: {precision}자리)")
        return adjusted
    else:
        # ⚠️ 경고: 캐싱되지 않은 경우 - 기본값 사용
        print(f"⚠️ {symbol} 정밀도 정보 없음! 기본값 사용 (소수점 3자리)")
        print(f"   💡 fetch_symbol_precision()을 먼저 호출하세요!")
        return max(round(quantity, 3), 0.001)


def adjust_price_precision(symbol, price):
    """
    심볼에 맞게 가격 정밀도 조정
    
    ⚠️ 주의: SYMBOL_PRECISION에 해당 심볼이 없으면 기본값 사용
    """
    if symbol in SYMBOL_PRECISION:
        precision = SYMBOL_PRECISION[symbol]['price']
        return round(price, precision)
    else:
        print(f"⚠️ {symbol} 가격 정밀도 정보 없음! 기본값 사용 (소수점 2자리)")
        return round(price, 2)
    

def get_binance_symbol(db_symbol):
    """DB 심볼을 바이낸스 심볼로 변환"""
    if db_symbol in SYMBOL_MAPPING:
        mapped = SYMBOL_MAPPING[db_symbol]
        if mapped is None:
            return None
        return mapped
    return db_symbol


class DatabaseWatcher(QThread):
    new_signal_detected = pyqtSignal(dict)
    status_changed = pyqtSignal(str)

    def __init__(self, db_config, active_strategies, scan_interval=10, target_date=None):
        super().__init__()
        self.db_config = db_config
        self.active_strategies = active_strategies
        self.is_watching = False
        self.last_signal_id = 0
        self.scan_interval = scan_interval
        self.target_date = target_date
        self.current_signals = {}

    def update_scan_interval(self, interval):
        self.scan_interval = interval
        print(f"🔄 SQL 순회 주기 변경: {interval}초")

    def update_target_date(self, date):
        self.target_date = date
        print(f"📅 대상 날짜 변경: {date}")

    def start_watching(self):
        self.is_watching = True
        self.get_last_signal_id()
        self.start()

    def stop_watching(self):
        self.is_watching = False

    def update_strategies(self, strategies):
        self.active_strategies = strategies

    def get_last_signal_id(self):
        try:
            connection = mysql.connector.connect(**self.db_config)
            cursor = connection.cursor()
            cursor.execute("SELECT MAX(id) FROM trading_signals")
            result = cursor.fetchone()
            self.last_signal_id = result[0] if result and result[0] else 0
            cursor.close()
            connection.close()
            print(f"📊 시작 ID: {self.last_signal_id}")
        except Exception as e:
            print(f"❌ ID 조회 실패: {e}")
            self.last_signal_id = 0

    def run(self):
        print(f"🤖 DB 감지 시작 (주기: {self.scan_interval}초, 날짜: {self.target_date})")
        while self.is_watching:
            try:
                self.check_new_signals()
                time.sleep(self.scan_interval)
            except Exception as e:
                print(f"❌ DB 감지 오류: {e}")
                time.sleep(5)


    # 1. DatabaseWatcher.check_new_signals() 수정
    def check_new_signals(self):
        try:
            connection = mysql.connector.connect(**self.db_config)
            cursor = connection.cursor(dictionary=True, buffered=True)
            
            if not self.active_strategies:
                cursor.close()
                connection.close()
                return
            
            strategy_list = list(self.active_strategies)
            placeholders = ','.join(['%s'] * len(strategy_list))
            
            if self.target_date:
                date_str = self.target_date.strftime('%Y-%m-%d') if not isinstance(self.target_date, str) else self.target_date
                
                query = f"""
                SELECT * FROM trading_signals 
                WHERE strategy_name IN ({placeholders})
                AND DATE_FORMAT(created_at, '%Y-%m-%d') = %s
                ORDER BY created_at DESC
                """
                params = strategy_list + [date_str]
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] SQL 스캔: {date_str}")
            else:
                query = f"""
                SELECT * FROM trading_signals 
                WHERE strategy_name IN ({placeholders}) 
                AND processed = FALSE 
                AND created_at >= DATE_SUB(NOW(), INTERVAL 5 MINUTE)
                ORDER BY created_at DESC
                """
                params = strategy_list
                print(f"[{datetime.now().strftime('%H:%M:%S')}] SQL 스캔: 실시간")
            
            cursor.execute(query, params)
            signals = cursor.fetchall()
            
            if len(signals) > 0:
                print(f"  → {len(signals)}개 시그널")

            if self.target_date:
                changed_signals = []
                
                for signal in signals:
                    symbol = signal['symbol']
                    signal_type = signal['signal_type']
                    
                    if symbol in self.current_signals:
                        old_signal = self.current_signals[symbol]
                        if old_signal != signal_type:
                            print(f"  변경: {symbol} {old_signal}→{signal_type}")
                            changed_signals.append(signal)
                    else:
                        print(f"  신규: {symbol} {signal_type}")
                        changed_signals.append(signal)
                    
                    self.current_signals[symbol] = signal_type
                
                if changed_signals:
                    print(f"  ✅ {len(changed_signals)}개 매매 실행")
                    self.status_changed.emit(f"BATCH_EXECUTE:{len(changed_signals)}")
            else:
                for signal in signals:
                    print(f"  신규: {signal['symbol']} {signal['signal_type']}")
                    self.new_signal_detected.emit(signal)
                    self.last_signal_id = signal['id']
                    
                    update_query = "UPDATE trading_signals SET processed = TRUE, processed_at = NOW() WHERE id = %s"
                    cursor.execute(update_query, (signal['id'],))
            
            connection.commit()
            cursor.close()
            connection.close()
        except Exception as e:
            print(f"❌ SQL 오류: {e}")


class StrategyWidget(QWidget):
    strategy_signal_received = pyqtSignal(dict)
    trade_executed = pyqtSignal()
    db_connected = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.client = None
        self.db_connection = None
        self.db_config = None
        self.db_watcher = None
        self.active_strategies = set()
        self.db_manager = None
        self.position_manager = None
        self.is_processing = False
        self.pending_execution = False  # 🔥 추가
        
        # 매매방식 변수 
        self.trading_mode = "CONSERVATIVE"  # "CONSERVATIVE" 또는 "AGGRESSIVE"
        self.trade_setting_widgets = []  # 거래 설정 위젯 리스트
        
        self.failed_orders_log = 'failed_orders.csv'
        self._ensure_log_directory()
        
        self.ai_strategies = ['AI_XGBOOST_PREDICTION', 'AI_LSTM_PREDICTION', 'AI_RANDOM_FOREST']
        self.quant_strategies = ['RSI_REVERSAL', 'MACD_MOMENTUM', 'BOLLINGER_BREAKOUT', 'EMA_CROSSOVER']
        
        self.init_ui()


    def init_ui(self):
        self.setMaximumWidth(420)
        layout = QVBoxLayout(self)
        
        # 제목 (항상 보임)
        title_label = QLabel("📊 전략 관리 (포지션 기반 자동매매)")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #00d4aa; margin: 10px;")
        layout.addWidget(title_label)

        # ========== DB 연결 섹션 (항상 보임) ==========
        db_group = QGroupBox("🗄️ 데이터베이스")
        db_layout = QVBoxLayout(db_group)
        
        self.db_status_label = QLabel("연결 상태: 미연결")
        self.db_status_label.setStyleSheet("color: #888888; font-weight: bold;")
        db_layout.addWidget(self.db_status_label)
        
        db_button_layout = QHBoxLayout()
        self.connect_db_button = QPushButton("DB 연결")
        self.connect_db_button.clicked.connect(self.on_connect_db_clicked)  # 🔥 수정
        self.connect_db_button.setStyleSheet("""
            QPushButton { background-color: #28a745; color: white; font-weight: bold; padding: 8px; border: none; border-radius: 3px; }
            QPushButton:hover { background-color: #218838; }
            QPushButton:disabled { background-color: #6c757d; color: #aaa; }
        """)
        db_button_layout.addWidget(self.connect_db_button)
        
        self.disconnect_db_button = QPushButton("DB 해제")
        self.disconnect_db_button.clicked.connect(self.disconnect_database)
        self.disconnect_db_button.setEnabled(False)
        self.disconnect_db_button.setStyleSheet("""
            QPushButton { background-color: #dc3545; color: white; font-weight: bold; padding: 8px; border: none; border-radius: 3px; }
            QPushButton:hover { background-color: #c82333; }
            QPushButton:disabled { background-color: #6c757d; color: #aaa; }
        """)
        db_button_layout.addWidget(self.disconnect_db_button)
        
        db_layout.addLayout(db_button_layout)
        layout.addWidget(db_group)

        # ========== 전략/설정 컨테이너 (처음에는 숨김) ==========
        self.strategy_container = QWidget()
        container_layout = QVBoxLayout(self.strategy_container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        # AI 전략
        ai_group = QGroupBox("🤖 AI 모델 전략")
        ai_layout = QVBoxLayout(ai_group)
        self.ai_strategy_list = QListWidget()
        self.ai_strategy_list.setMaximumHeight(100)
        for strategy in self.ai_strategies:
            item = QListWidgetItem(strategy)
            item.setCheckState(Qt.Unchecked)
            self.ai_strategy_list.addItem(item)
        self.ai_strategy_list.itemChanged.connect(self.on_strategy_selected)
        ai_layout.addWidget(self.ai_strategy_list)
        
        ai_button_layout = QHBoxLayout()
        self.select_all_ai_button = QPushButton("AI 전체 선택")
        self.deselect_all_ai_button = QPushButton("AI 전체 해제")
        self.select_all_ai_button.clicked.connect(lambda: self.toggle_all_strategies(self.ai_strategy_list, True))
        self.deselect_all_ai_button.clicked.connect(lambda: self.toggle_all_strategies(self.ai_strategy_list, False))
        ai_button_layout.addWidget(self.select_all_ai_button)
        ai_button_layout.addWidget(self.deselect_all_ai_button)
        ai_layout.addLayout(ai_button_layout)
        container_layout.addWidget(ai_group)

        # 퀀트 전략
        quant_group = QGroupBox("📈 퀀트 전략")
        quant_layout = QVBoxLayout(quant_group)
        self.quant_strategy_list = QListWidget()
        self.quant_strategy_list.setMaximumHeight(100)
        for strategy in self.quant_strategies:
            item = QListWidgetItem(strategy)
            item.setCheckState(Qt.Unchecked)
            self.quant_strategy_list.addItem(item)
        self.quant_strategy_list.itemChanged.connect(self.on_strategy_selected)
        quant_layout.addWidget(self.quant_strategy_list)
        
        quant_button_layout = QHBoxLayout()
        self.select_all_quant_button = QPushButton("퀀트 전체 선택")
        self.deselect_all_quant_button = QPushButton("퀀트 전체 해제")
        self.select_all_quant_button.clicked.connect(lambda: self.toggle_all_strategies(self.quant_strategy_list, True))
        self.deselect_all_quant_button.clicked.connect(lambda: self.toggle_all_strategies(self.quant_strategy_list, False))
        quant_button_layout.addWidget(self.select_all_quant_button)
        quant_button_layout.addWidget(self.deselect_all_quant_button)
        quant_layout.addLayout(quant_button_layout)
        container_layout.addWidget(quant_group)

        # 포지션 관리
        position_group = QGroupBox("📊 포지션 관리")
        position_layout = QVBoxLayout(position_group)
        
        max_pos_layout = QHBoxLayout()
        max_pos_layout.addWidget(QLabel("최대 포지션 수:"))
        self.max_positions_spinbox = QSpinBox()
        self.max_positions_spinbox.setRange(1, 10)
        self.max_positions_spinbox.setValue(5)
        self.max_positions_spinbox.setSuffix("개")
        self.max_positions_spinbox.valueChanged.connect(self.on_max_positions_changed)
        max_pos_layout.addWidget(self.max_positions_spinbox)
        position_layout.addLayout(max_pos_layout)
        
        self.current_positions_label = QLabel("현재 포지션: 0 / 5")
        self.current_positions_label.setStyleSheet("color: #00d4aa; font-weight: bold; padding: 5px;")
        position_layout.addWidget(self.current_positions_label)
        container_layout.addWidget(position_group)

        # 거래 설정
        trade_group = QGroupBox("💰 거래 설정")
        trade_layout = QVBoxLayout(trade_group)
        
        # 증거금/레버리지 설정
        self.usdt_layout = QHBoxLayout()
        self.usdt_layout.addWidget(QLabel("증거금(USDT):"))
        self.usdt_amount = QDoubleSpinBox()
        self.usdt_amount.setRange(10, 100000)
        self.usdt_amount.setValue(100)
        self.usdt_amount.setDecimals(2)
        self.usdt_layout.addWidget(self.usdt_amount)
        
        # MAX 버튼 추가
        self.max_balance_button = QPushButton("MAX")
        self.max_balance_button.setMaximumWidth(60)
        self.max_balance_button.setStyleSheet("QPushButton { background-color: #ff9800; }")
        self.max_balance_button.clicked.connect(lambda: asyncio.create_task(self.set_max_available_balance()))
        self.usdt_layout.addWidget(self.max_balance_button)
        trade_layout.addLayout(self.usdt_layout)
        
        self.leverage_layout = QHBoxLayout()
        self.leverage_layout.addWidget(QLabel("레버리지:"))
        self.leverage_slider = QSlider(Qt.Horizontal)
        self.leverage_slider.setRange(1, 20)
        self.leverage_slider.setValue(10)
        self.leverage_slider.valueChanged.connect(self.update_position_value_display)
        self.leverage_layout.addWidget(self.leverage_slider)
        self.leverage_label = QLabel("10x")
        self.leverage_layout.addWidget(self.leverage_label)
        trade_layout.addLayout(self.leverage_layout)
        
        self.total_value_label = QLabel("총 포지션 가치: 1,000.00 USDT")
        self.total_value_label.setStyleSheet("color: #ffa500; font-weight: bold;")
        trade_layout.addWidget(self.total_value_label)
        
        container_layout.addWidget(trade_group)

        # 매매방식
        trading_mode_group = QGroupBox("⚙️ 매매 방식")
        trading_mode_layout = QHBoxLayout()
        self.conservative_radio = QRadioButton("보수 (롱만)")
        self.aggressive_radio = QRadioButton("공격 (양방향)")
        self.conservative_radio.setChecked(True)
        self.conservative_radio.toggled.connect(self.on_trading_mode_changed)
        trading_mode_layout.addWidget(self.conservative_radio)
        trading_mode_layout.addWidget(self.aggressive_radio)
        trading_mode_layout.addStretch()
        trading_mode_group.setLayout(trading_mode_layout)
        container_layout.addWidget(trading_mode_group)

        # 제어
        control_group = QGroupBox("🎮 제어")
        control_layout = QVBoxLayout(control_group)

        # ⭐ 이 부분을 추가 ⭐
        # SQL 스캔 간격 설정
        scan_layout = QHBoxLayout()
        scan_layout.addWidget(QLabel("SQL 순회 주기:"))
        self.sql_scan_interval = QSpinBox()
        self.sql_scan_interval.setRange(5, 60)
        self.sql_scan_interval.setValue(10)
        self.sql_scan_interval.setSuffix("초")
        scan_layout.addWidget(self.sql_scan_interval)
        control_layout.addLayout(scan_layout)

        # 대상 날짜 설정
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("대상 날짜:"))
        self.target_date = QDateEdit()
        self.target_date.setCalendarPopup(True)
        self.target_date.setDate(QDate.currentDate())
        date_layout.addWidget(self.target_date)
        control_layout.addLayout(date_layout)
        
        # 수동 제어
        manual_layout = QHBoxLayout()
        self.call_signal_button = QPushButton("📊 시그널 호출")
        self.call_signal_button.clicked.connect(self.call_latest_signal)
        manual_layout.addWidget(self.call_signal_button)
        control_layout.addLayout(manual_layout)
        
        # 자동매매
        auto_layout = QHBoxLayout()
        self.start_auto_button = QPushButton("🤖 자동매매 시작")
        self.stop_auto_button = QPushButton("⏹️ 자동매매 중지")
        self.stop_auto_button.setEnabled(False)
        self.start_auto_button.clicked.connect(self.start_auto_trading)
        self.stop_auto_button.clicked.connect(self.stop_auto_trading)
        auto_layout.addWidget(self.start_auto_button)
        auto_layout.addWidget(self.stop_auto_button)
        control_layout.addLayout(auto_layout)
        container_layout.addWidget(control_group)

        # 상태
        status_group = QGroupBox("📡 시그널 상태")
        status_layout = QVBoxLayout(status_group)
        self.signal_status_label = QLabel("상태: 대기 중")
        status_layout.addWidget(self.signal_status_label)
        self.last_signal_label = QLabel("마지막 시그널: 없음")
        status_layout.addWidget(self.last_signal_label)
        self.signal_time_label = QLabel("시그널 시간: -")
        status_layout.addWidget(self.signal_time_label)
        self.auto_status_label = QLabel("자동매매: 중지")
        status_layout.addWidget(self.auto_status_label)
        container_layout.addWidget(status_group)

        # 컨테이너를 메인 레이아웃에 추가하고 숨김
        layout.addWidget(self.strategy_container)
        self.strategy_container.hide()  # 🔥 처음에는 숨김

        self.apply_styles()

    # 🔥 DB 연결 버튼 클릭 시
    def on_connect_db_clicked(self):
        """DB 연결 버튼 클릭"""
        self.connect_database()
        
        # DB 연결 성공 시 전략/설정 표시
        if self.db_connection and self.db_connection.is_connected():
            self.strategy_container.show()  # 🔥 나머지 UI 표시
            print("✅ 전략/설정 UI 표시됨")

    # disconnect_database 함수에 추가
    def disconnect_database(self):
        """데이터베이스 연결 해제"""
        try:
            # ... 기존 해제 로직 전체 유지 ...
            
            # 🔥 마지막에 추가: 전략/설정 숨김
            self.strategy_container.hide()
            print("✅ 전략/설정 UI 숨김")
            
        except Exception as e:
            print(f"❌ DB 해제 실패: {e}")

    def apply_styles(self):
        self.setStyleSheet("""
            QGroupBox { 
                font-weight: bold; 
                border: 2px solid #555; 
                border-radius: 8px; 
                margin-top: 10px; 
                background-color: #2c2c2c; 
                color: white; 
                padding-top: 10px; 
            }
            QGroupBox::title { 
                subcontrol-origin: margin; 
                left: 10px; 
                padding: 0 5px 0 5px; 
                color: #00d4aa; 
            }
            QListWidget { 
                background-color: #1e1e1e;
                border: 1px solid #555; 
                border-radius: 5px; 
                color: white;
                alternate-background-color: #252525;
            }
            QListWidget::item {
                padding: 5px;
                color: white;
                background-color: transparent;
            }
            QListWidget::item:hover {
                background-color: #2d2d2d;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QPushButton { 
                background-color: #0078d4; 
                border: none; 
                border-radius: 5px; 
                padding: 8px; 
                color: white; 
                font-weight: bold; 
            }
            QPushButton:hover { 
                background-color: #106ebe; 
            }
            QPushButton:disabled { 
                background-color: #555; 
                color: #aaa; 
            }
            QLabel { 
                color: white; 
                padding: 2px; 
            }
            QCheckBox {
                color: white;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                background-color: #3c3c3c;
                border: 1px solid #666;
                border-radius:border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border: 1px solid #0078d4;
            }
            QRadioButton { 
                color: white; 
            }
            QSpinBox, QDoubleSpinBox { 
                background-color: #3c3c3c; 
                border: 1px solid #555; 
                border-radius: 3px; 
                color: white; 
                padding: 5px; 
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                background-color: #555;
                border: none;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                background-color: #555;
                border: none;
            }
            QComboBox { 
                background-color: #3c3c3c; 
                border: 1px solid #555; 
                border-radius: 3px; 
                color: white; 
                padding: 5px; 
            }
            QComboBox QAbstractItemView {
                background-color: #2c2c2c;
                color: white;
                selection-background-color: #0078d4;
                selection-color: white;
                border: 1px solid #555;
            }
            QComboBox::drop-down {
                border: none;
                background-color: #555;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid white;
                margin-right: 5px;
            }
            QSlider::groove:horizontal { 
                border: 1px solid #bbb; 
                background: white; 
                height: 8px; 
                border-radius: 4px; 
            }
            QSlider::handle:horizontal { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #eee, stop:1 #ccc); 
                border: 1px solid #777; 
                width: 18px; 
                margin: -2px 0; 
                border-radius: 9px; 
            }
        """)

    def on_trading_mode_changed(self):
        """매매방식 변경 핸들러"""
        if self.conservative_radio.isChecked():
            self.trading_mode = "CONSERVATIVE"
            print("📊 매매방식: 보수 (롱만 진입)")
        else:
            self.trading_mode = "AGGRESSIVE"
            print("📊 매매방식: 공격 (양방향)")

    def on_max_positions_changed(self, value):
        """최대 포지션 수 변경 시 position_manager 업데이트"""
        if self.position_manager:
            self.position_manager.max_positions = value
            print(f"✅ 최대 포지션 수 변경: {value}개")
            
            # 포지션 표시 업데이트
            asyncio.create_task(self.update_position_display())

    async def conservative_mode_execute(self, valid_signals, current_positions):
        """보수 모드: 롱만 진입, 숏 시그널 시 청산"""
        print("\n📘 [보수 모드] 시작")
        
        # [1단계] 기존 포지션 관리
        print("   [1단계] 기존 포지션 관리")
        for symbol, position_data in list(current_positions.items()):
            if symbol not in valid_signals:
                print(f"      - {symbol}: 시그널 없음 → 유지")
                continue
            
            signal = valid_signals[symbol]
            signal_type = signal['signal_type']
            
            if signal_type == 'HOLD':
                print(f"      - {symbol}: HOLD → 유지")
                continue
            
            # 롱 포지션 보유 중
            if position_data['side'] == 'LONG':
                if signal_type == 'LONG':
                    print(f"      - {symbol}: 롱 유지")
                    continue
                elif signal_type == 'SHORT':
                    # 🔥 핵심: 숏 시그널 → 청산만
                    print(f"      - {symbol}: 숏 시그널 → 롱 청산")
                    await self.close_position_only(symbol, position_data)
            
            # 숏 포지션 보유 시 (보수 모드에서는 이론적으로 없음)
            elif position_data['side'] == 'SHORT':
                print(f"      - {symbol}: 숏 포지션 청산 (보수 모드)")
                await self.close_position_only(symbol, position_data)
            
            await asyncio.sleep(2)
        
        # [2단계] 신규 롱 진입만
        print("\n   [2단계] 신규 롱 진입 검토")
        await self.position_manager.get_current_positions()
        current_positions = self.position_manager.active_positions
        
        if len(current_positions) >= self.position_manager.max_positions:
            print(f"      ⚠️ 최대 포지션 도달")
            return
        
        new_count = 0
        
        # 🔥 수정: 롱 시그널만 필터링해서 진입
        long_signals = {sym: sig for sym, sig in valid_signals.items() 
                        if sig['signal_type'] == 'LONG'}
        
        print(f"   📊 롱 시그널: {len(long_signals)}개 발견")
        
        for symbol, signal in long_signals.items():
            if len(current_positions) >= self.position_manager.max_positions:
                break
            
            if symbol in current_positions:
                continue
            
            print(f"      - {symbol}: 롱 진입 시도")
            success = await self.open_position(signal)
            if success:
                new_count += 1
                print(f"      - ✅ {symbol}: 롱 진입 성공")
                await self.position_manager.get_current_positions()
                current_positions = self.position_manager.active_positions
            else:
                print(f"      - ❌ {symbol}: 롱 진입 실패")
            
            await asyncio.sleep(2)
        
        # 숏 시그널은 무시 (로그만 출력)
        short_signals = {sym: sig for sym, sig in valid_signals.items() 
                        if sig['signal_type'] == 'SHORT'}
        if short_signals:
            print(f"\n   📊 숏 시그널 {len(short_signals)}개 무시 (보수 모드)")
            for symbol in short_signals.keys():
                print(f"      - {symbol}: 숏 시그널 무시")
        
        print(f"\n   ✅ 보수 모드 완료 - 신규 롱: {new_count}개")
        
    # ==================== 6. 공격 모드 실행 함수 추가 ====================
    async def aggressive_mode_execute(self, valid_signals, current_positions):
        """공격 모드: 양방향 전환 (기존 로직)"""
        print("\n🔥 [공격 모드] 시작")
        
        # [1단계] 기존 포지션 관리
        print("   [1단계] 기존 포지션 관리")
        for symbol, position_data in list(current_positions.items()):
            if symbol not in valid_signals:
                print(f"      - {symbol}: 시그널 없음 → 유지")
                continue
            
            signal = valid_signals[symbol]
            signal_type = signal['signal_type']
            
            if signal_type == 'HOLD':
                print(f"      - {symbol}: HOLD → 유지")
                continue
            
            if signal_type == position_data['side']:
                print(f"      - {symbol}: 방향 일치 → 유지")
                continue
            
            # 반대 방향 → 포지션 전환
            print(f"      - {symbol}: 전환 ({position_data['side']} → {signal_type})")
            await self.close_and_open(symbol, position_data, signal)
            await asyncio.sleep(2)
        
        # [2단계] 신규 진입 (롱/숏 모두)
        print("\n   [2단계] 신규 진입")
        await self.position_manager.get_current_positions()
        current_positions = self.position_manager.active_positions
        
        if len(current_positions) >= self.position_manager.max_positions:
            print(f"      ⚠️ 최대 포지션 도달")
            return
        
        new_count = 0
        for symbol, signal in valid_signals.items():
            if len(current_positions) >= self.position_manager.max_positions:
                break
            
            if symbol in current_positions:
                continue
            
            signal_type = signal['signal_type']
            
            if signal_type == 'HOLD':
                print(f"      - {symbol}: HOLD 스킵")
                continue
            
            # 공격 모드: 롱/숏 모두 진입
            print(f"      - {symbol}: {signal_type} 진입 시도")
            success = await self.open_position(signal)
            if success:
                new_count += 1
                await self.position_manager.get_current_positions()
                current_positions = self.position_manager.active_positions
            
            await asyncio.sleep(2)
        
        print(f"\n   ✅ 공격 모드 완료 - 신규 진입: {new_count}개")

    async def close_position_manual(self, symbol, position_data):
        """
        수동 청산 함수 (Position Widget의 청산 버튼용)
        
        이 함수를 통해 청산하면 자동매매가 해당 심볼을 다시 진입하지 않음
        """
        try:
            # 기존 청산 로직
            close_qty = position_data['quantity']
            close_side = 'SELL' if position_data['side'] == 'LONG' else 'BUY'
            close_qty = adjust_quantity_precision(symbol, close_qty)
            
            print(f"🖐️ [수동 청산] {symbol} {position_data['side']} {close_qty}")
            
            result = await self.client.place_order(
                symbol=symbol, side=close_side, order_type='MARKET', quantity=close_qty
            )
            
            if result and 'orderId' in result:
                print(f"✅ 수동 청산 성공")
                
                # 🔥 수동 청산 기록 저장
                self.manually_closed_symbols.add(symbol)
                self.manual_close_times[symbol] = datetime.now()
                print(f"📝 {symbol} 수동 청산 기록됨 (자동 재진입 차단)")
                
                # DB 저장 등 나머지 로직...
                if self.db_manager:
                    pnl = position_data['unrealized_pnl']
                    self.db_manager.save_trade({
                        'order_id': result['orderId'],
                        'symbol': symbol,
                        'side': position_data['side'],
                        'trade_type': 'EXIT',
                        'quantity': close_qty,
                        'price': position_data.get('entry_price', 0),
                        'leverage': position_data.get('leverage', self.leverage_slider.value()),
                        'realized_pnl': pnl,
                        'commission': 0,
                        'trade_time': datetime.now()
                    })
                
                self.trade_executed.emit()
                await asyncio.sleep(2)
                await self.position_manager.get_current_positions()
                return True
            else:
                print(f"❌ 수동 청산 실패")
                return False
                
        except Exception as e:
            print(f"❌ 수동 청산 중 오류: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ==================== 7. 청산 전용 함수 추가 ====================
    async def close_position_only(self, symbol, position_data):
        """포지션 청산만 (재진입 없음)"""
        try:
            close_qty = position_data['quantity']
            close_side = 'SELL' if position_data['side'] == 'LONG' else 'BUY'
            close_qty = adjust_quantity_precision(symbol, close_qty)
            
            print(f"  📤 청산 주문: {symbol} {close_side} {close_qty}")
            
            result = await self.client.place_order(
                symbol=symbol, 
                side=close_side, 
                order_type='MARKET', 
                quantity=close_qty
            )
            
            if result and 'orderId' in result:
                order_id = result['orderId']
                print(f"  ✅ 청산 성공: ID {order_id}")
                
                # 체결 정보 조회
                await asyncio.sleep(2)
                fill_info = await self.get_fill_info(symbol, order_id)
                
                if fill_info and self.db_manager:
                    # 손익 계산
                    entry_price = position_data['entry_price']
                    exit_price = fill_info['avgPrice']
                    qty = fill_info['executedQty']
                    
                    if position_data['side'] == 'LONG':
                        pnl = (exit_price - entry_price) * qty
                    else:
                        pnl = (entry_price - exit_price) * qty
                    
                    # DB 저장
                    trade_data = {
                        'order_id': str(order_id),
                        'symbol': symbol,
                        'side': position_data['side'],
                        'trade_type': 'EXIT',
                        'quantity': qty,
                        'price': exit_price,
                        'leverage': position_data.get('leverage', 1),
                        'commission': fill_info['commission'],
                        'realized_pnl': pnl,
                        'trade_time': datetime.now()
                    }
                    self.db_manager.save_trade(trade_data)
                
                # 🔥 거래 실행 시그널 발송 (포지션 즉시 업데이트)
                self.trade_executed.emit()
                
                return True
            else:
                print(f"  ❌ 청산 실패")
                return False
                
        except Exception as e:
            print(f"청산 실패: {e}")
            return False

    async def scan_and_execute_trades(self):
        """자동매매 스캔 및 실행 (수정 버전)"""
        if self.is_processing:
            print("⚠️ 이미 처리 중")
            return
        
        self.is_processing = True
        
        try:
            print("\n" + "="*70)
            print(f"🔍 자동매매 스캔 시작 (모드: {self.trading_mode})")
            print("="*70)
            
            # DB에서 시그널 조회
            signals = await self.get_latest_signals_from_db()
            
            if not signals:
                print("⚠️ 유효한 시그널 없음")
                self.is_processing = False
                return
            
            print(f"📊 조회된 시그널: {len(signals)}개")
            
            # 심볼별 최신 시그널
            latest_signals = {}
            for signal in signals:
                symbol = signal['symbol']
                if symbol not in latest_signals:
                    latest_signals[symbol] = signal
            
            # 바이낸스 심볼 변환
            valid_signals = {}
            for symbol, signal in latest_signals.items():
                binance_symbol = get_binance_symbol(symbol)
                if binance_symbol is None:
                    print(f"   ⚠️ {symbol}: 바이낸스 미지원")
                    continue
                
                if binance_symbol != symbol:
                    print(f"   🔄 {symbol} -> {binance_symbol}")
                
                signal['binance_symbol'] = binance_symbol
                valid_signals[binance_symbol] = signal
            
            print(f"✅ 유효한 시그널: {len(valid_signals)}개")
            
            # 보수 모드: 숏 시그널 제거
            if self.trading_mode == "CONSERVATIVE":
                removed = [s for s, sig in list(valid_signals.items()) if sig['signal_type'] == 'SHORT']
                valid_signals = {s: sig for s, sig in valid_signals.items() if sig['signal_type'] != 'SHORT'}
                if removed:
                    print(f"🚫 보수 모드: 숏 시그널 제거 ({len(removed)}개)")
            
            # 🔥 수동 청산된 심볼 제외
            if self.manually_closed_symbols:
                before_count = len(valid_signals)
                valid_signals = {
                    s: sig for s, sig in valid_signals.items() 
                    if s not in self.manually_closed_symbols
                }
                removed_count = before_count - len(valid_signals)
                if removed_count > 0:
                    print(f"🖐️ 수동 청산 심볼 제외: {removed_count}개")
                    print(f"   제외된 심볼: {self.manually_closed_symbols}")
            
            # 현재 포지션 조회
            await self.position_manager.get_current_positions()
            current_positions = self.position_manager.active_positions
            
            print(f"\n📊 현재 포지션: {len(current_positions)}개")
            print(f"📊 처리할 시그널: {len(valid_signals)}개")
            
            # [1단계] 기존 포지션 처리
            print(f"\n[1단계] 기존 포지션 처리")
            for symbol, position_data in list(current_positions.items()):
                if symbol not in valid_signals:
                    continue
                
                signal = valid_signals[symbol]
                signal_type = signal['signal_type']
                
                if signal_type == 'HOLD':
                    continue
                
                # 보수 모드
                if self.trading_mode == "CONSERVATIVE":
                    if position_data['side'] == 'LONG' and signal_type == 'LONG':
                        continue
                    elif position_data['side'] == 'LONG':
                        print(f"{symbol}: 롱 청산")
                        await self.close_position_only(symbol, position_data)
                        continue
                    elif position_data['side'] == 'SHORT':
                        print(f"{symbol}: 숏 청산")
                        await self.close_position_only(symbol, position_data)
                        continue
                
                # 공격 모드
                if signal_type == position_data['side']:
                    continue
                
                print(f"{symbol}: {position_data['side']}→{signal_type}")
                await self.close_and_open(symbol, position_data, signal)
                await asyncio.sleep(1)
            
            # 포지션 재조회
            await self.position_manager.get_current_positions()
            current_positions = self.position_manager.active_positions
            
            # [2단계] 신규 진입
            print(f"\n[신규 진입]")
            
            if len(current_positions) >= self.position_manager.max_positions:
                print(f"최대 도달 ({len(current_positions)}/{self.position_manager.max_positions})")
                return
            
            available_slots = self.position_manager.max_positions - len(current_positions)
            print(f"가능: {available_slots}개")
            
            new_entry_count = 0
            for symbol, signal in valid_signals.items():
                if len(current_positions) >= self.position_manager.max_positions:
                    break
                
                if symbol in current_positions:
                    continue
                
                signal_type = signal['signal_type']
                
                if signal_type == 'HOLD':
                    continue
                
                # 🔥 수동 청산된 심볼은 재진입 안 함
                if symbol in self.manually_closed_symbols:
                    print(f"{symbol}: 수동 청산 기록 있음 - 재진입 차단")
                    continue
                
                # 보수 모드
                if self.trading_mode == "CONSERVATIVE" and signal_type != 'LONG':
                    print(f"{symbol}: 숏 진입 차단 (보수 모드)")
                    continue
                
                print(f"{symbol}: {signal_type} 진입")
                
                success = await self.open_position(signal)
                if success:
                    new_entry_count += 1
                    await self.position_manager.get_current_positions()
                    current_positions = self.position_manager.active_positions
                
                await asyncio.sleep(1)
            
            print(f"\n완료: 신규 {new_entry_count}개, 총 {len(current_positions)}개")
            print(f"{'='*50}\n")
        
        except Exception as e:
            print(f"❌ 오류: {e}")
        finally:
            self.is_processing = False

    def _ensure_log_directory(self):
        """CSV 헤더 초기화 (같은 폴더에 저장)"""
        try:
            # CSV 파일이 없으면 헤더 생성
            if not Path(self.failed_orders_log).exists():
                with open(self.failed_orders_log, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'timestamp',
                        'symbol',
                        'signal_type',
                        'reason',
                        'price',
                        'calculated_quantity',
                        'min_quantity',
                        'min_notional',
                        'total_margin',
                        'margin_per_symbol',
                        'leverage',
                        'max_positions'
                    ])
                print(f"✅ 실패 로그 파일 생성: {self.failed_orders_log}")
        except Exception as e:
            print(f"⚠️ 로그 파일 생성 실패: {e}")

    def log_failed_order(self, symbol, signal_type, reason, details=None):
        """
        주문 실패 로그를 CSV에 저장
        
        Args:
            symbol: 심볼
            signal_type: 시그널 타입 (LONG/SHORT)
            reason: 실패 사유
            details: 추가 정보 (dict)
        """
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 기본값 설정
            if details is None:
                details = {}
            
            row = [
                timestamp,
                symbol,
                signal_type,
                reason,
                details.get('price', 0),
                details.get('calculated_quantity', 0),
                details.get('min_quantity', 0),
                details.get('min_notional', 0),
                details.get('total_margin', 0),
                details.get('margin_per_symbol', 0),
                details.get('leverage', 0),
                details.get('max_positions', 0)
            ]
            
            with open(self.failed_orders_log, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
            
            print(f"📝 실패 로그 저장: {symbol} - {reason}")
            
        except Exception as e:
            print(f"⚠️ 로그 저장 실패: {e}")

    async def set_max_available_balance(self):
        """
        사용가능한 전체 증거금을 자동으로 설정 (MAX 버튼)
        """
        # 🔥 API 연동 확인 추가!
        if not self.client:
            QMessageBox.warning(
                self, 
                "API 연동 필요", 
                "먼저 바이낸스 API를 연결해주세요.\n\n"
                "Account Widget에서 API Key를 입력하고\n"
                "'연결' 버튼을 클릭하세요."
            )
            return
        
        try:
            print("\n" + "="*70)
            print("💰 사용가능 증거금 조회 중...")
            print("="*70)
            
            # 계정 정보 조회
            account_info = await self.client.get_account_info()
            if not account_info:
                QMessageBox.warning(self, "오류", "계정 정보를 가져올 수 없습니다.\nAPI 연결을 확인해주세요.")
                return
            
            # 사용가능 증거금 추출
            available_balance = float(account_info.get('availableBalance', 0))
            
            print(f"   총 사용가능 증거금: {available_balance:.2f} USDT")
            
            if available_balance <= 10:
                QMessageBox.warning(
                    self, 
                    "증거금 부족", 
                    f"사용가능한 증거금이 부족합니다.\n\n"
                    f"현재 잔액: {available_balance:.2f} USDT\n"
                    f"최소 필요: 10.00 USDT"
                )
                return
            
            # 🔥 안전마진 5% 제외
            safe_balance = available_balance * 0.95
            
            self.usdt_amount.setValue(safe_balance)
            
            print(f"   설정된 증거금: {safe_balance:.2f} USDT (5% 안전마진 적용)")
            print("="*70 + "\n")
            
            QMessageBox.information(
                self, 
                "증거금 설정 완료",
                f"사용가능 증거금이 설정되었습니다.\n\n"
                f"전체: {available_balance:.2f} USDT\n"
                f"설정: {safe_balance:.2f} USDT (95%)\n"
                f"안전마진: {available_balance - safe_balance:.2f} USDT (5%)"
            )
            
        except Exception as e:
            print(f"❌ 사용가능 증거금 설정 실패: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self, 
                "오류", 
                f"증거금 설정 중 오류가 발생했습니다:\n\n{str(e)}\n\n"
                f"API 연결 상태를 확인해주세요."
            )


    async def set_max_available_balance(self):
        """
        사용가능한 전체 증거금을 자동으로 설정 (MAX 버튼)
        """
        # 🔥 API 연동 확인 추가!
        if not self.client:
            QMessageBox.warning(
                self, 
                "API 연동 필요", 
                "먼저 바이낸스 API를 연결해주세요.\n\n"
                "Account Widget에서 API Key를 입력하고\n"
                "'연결' 버튼을 클릭하세요."
            )
            return
        
        try:
            print("\n" + "="*70)
            print("💰 사용가능 증거금 조회 중...")
            print("="*70)
            
            # 계정 정보 조회
            account_info = await self.client.get_account_info()
            if not account_info:
                QMessageBox.warning(self, "오류", "계정 정보를 가져올 수 없습니다.\nAPI 연결을 확인해주세요.")
                return
            
            # 사용가능 증거금 추출
            available_balance = float(account_info.get('availableBalance', 0))
            
            print(f"   총 사용가능 증거금: {available_balance:.2f} USDT")
            
            if available_balance <= 10:
                QMessageBox.warning(
                    self, 
                    "증거금 부족", 
                    f"사용가능한 증거금이 부족합니다.\n\n"
                    f"현재 잔액: {available_balance:.2f} USDT\n"
                    f"최소 필요: 10.00 USDT"
                )
                return
            
            # 🔥 안전마진 5% 제외
            safe_balance = available_balance * 0.95
            
            self.usdt_amount.setValue(safe_balance)
            
            print(f"   설정된 증거금: {safe_balance:.2f} USDT (5% 안전마진 적용)")
            print("="*70 + "\n")
            
            QMessageBox.information(
                self, 
                "증거금 설정 완료",
                f"사용가능 증거금이 설정되었습니다.\n\n"
                f"전체: {available_balance:.2f} USDT\n"
                f"설정: {safe_balance:.2f} USDT (95%)\n"
                f"안전마진: {available_balance - safe_balance:.2f} USDT (5%)"
            )
            
        except Exception as e:
            print(f"❌ 사용가능 증거금 설정 실패: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self, 
                "오류", 
                f"증거금 설정 중 오류가 발생했습니다:\n\n{str(e)}\n\n"
                f"API 연결 상태를 확인해주세요."
            )

    def update_position_value_display(self):
        leverage = self.leverage_slider.value()
        margin = self.usdt_amount.value()
        self.leverage_label.setText(f"{leverage}x")
        total_value = margin * leverage
        self.total_value_label.setText(f"총 포지션 가치: {total_value:,.2f} USDT")

    def on_amount_type_changed(self):
        is_usdt_mode = self.usdt_radio.isChecked()
        for w in [self.usdt_amount, self.leverage_slider, self.leverage_label, self.total_value_label]:
            w.setVisible(is_usdt_mode)
        for i in range(self.usdt_layout.count()):
            widget = self.usdt_layout.itemAt(i).widget()
            if widget: widget.setVisible(is_usdt_mode)
        for i in range(self.leverage_layout.count()):
            widget = self.leverage_layout.itemAt(i).widget()
            if widget: widget.setVisible(is_usdt_mode)
        for i in range(self.quantity_layout.count()):
            widget = self.quantity_layout.itemAt(i).widget()
            if widget: widget.setVisible(not is_usdt_mode)

    def toggle_all_strategies(self, list_widget, select_all):
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            item.setCheckState(Qt.Checked if select_all else Qt.Unchecked)

    def set_client(self, client):
        """바이낸스 클라이언트 설정 (완전 안전 버전)"""
        self.client = client
        
        max_pos = 5
        
        try:
            if hasattr(self, 'max_positions_spinbox') and self.max_positions_spinbox is not None:
                try:
                    max_pos = self.max_positions_spinbox.value()
                except RuntimeError:
                    print("⚠️ max_positions_spinbox 접근 실패 (기본값 5 사용)")
        except Exception as e:
            print(f"⚠️ max_positions_spinbox 오류 (기본값 사용): {e}")
        
        try:
            self.position_manager = PositionManager(client, max_pos)
        except Exception as e:
            print(f"⚠️ PositionManager 생성 실패: {e}")
            return
        
        try:
            asyncio.create_task(self.update_position_display())
        except Exception as e:
            print(f"⚠️ update_position_display 실패: {e}")

    async def update_position_display(self):
        if self.position_manager:
            try:
                await self.position_manager.get_current_positions()
                count = len(self.position_manager.active_positions)
                max_pos = self.max_positions_spinbox.value()
                self.current_positions_label.setText(f"현재 포지션: {count} / {max_pos}")
            except:
                pass

    def connect_database(self):
        """데이터베이스 연결"""
        try:
            print("\n" + "="*70)
            print("🔌 DB 연결 시도 중...")
            print("="*70)
            
            self.db_config = {
                'host': 'localhost',
                'database': 'trading_signals',
                'user': 'root',
                'password': 'ghkd2759A!'
            }
            
            self.db_connection = mysql.connector.connect(**self.db_config)
            
            if self.db_connection.is_connected():
                self.db_status_label.setText("✅ 연결됨")
                self.db_status_label.setStyleSheet("color: #00ff00; font-weight: bold;")
                
                self.connect_db_button.setEnabled(False)
                self.disconnect_db_button.setEnabled(True)
                
                self.db_manager = DatabaseManager(self.db_config)
                
                self.db_connected.emit(self.db_config)
                
                self.test_db_connection()
                
                print("="*70)
                print("✅ DB 연결 완료")
                print("="*70 + "\n")
                
                QMessageBox.information(self, "DB 연결 성공", "데이터베이스에 성공적으로 연결되었습니다.")
                
        except Exception as e:
            self.db_status_label.setText("❌ 연결 실패")
            self.db_status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
            
            print("="*70)
            print(f"❌ DB 연결 실패: {e}")
            print("="*70 + "\n")
            
            import traceback
            traceback.print_exc()
            
            QMessageBox.critical(
                self, "DB 연결 실패", 
                f"데이터베이스 연결에 실패했습니다.\n\n에러: {str(e)}\n\n"
                f"확인사항:\n"
                f"1. MySQL 서버가 실행 중인지 확인\n"
                f"2. 데이터베이스 'trading_signals' 존재 여부\n"
                f"3. 사용자 계정 및 비밀번호 확인"
            )

    def disconnect_database(self):
        """데이터베이스 연결 해제"""
        try:
            print("\n" + "="*70)
            print("🔌 DB 연결 해제 중...")
            print("="*70)
            
            if self.db_watcher and self.db_watcher.is_watching:
                reply = QMessageBox.question(
                    self, 
                    "⚠️ 자동매매 실행 중", 
                    "자동매매가 실행 중입니다.\n"
                    "DB 연결을 해제하면 자동매매가 중지됩니다.\n\n"
                    "계속하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.No:
                    print("   ℹ️ 사용자가 취소했습니다.")
                    return
                
                print("   🛑 자동매매 중지 중...")
                self.stop_auto_trading()
            
            if self.db_watcher:
                print("   🛑 DB Watcher 중지 중...")
                self.db_watcher.stop_watching()
                self.db_watcher = None
            
            if self.db_manager:
                print("   🗑️ DB Manager 정리 중...")
                self.db_manager = None
            
            if self.db_connection:
                try:
                    if self.db_connection.is_connected():
                        self.db_connection.close()
                        print("   ✅ DB 연결 종료 완료")
                except Exception as e:
                    print(f"   ⚠️ DB 연결 종료 중 오류 (무시): {e}")
                finally:
                    self.db_connection = None
            
            self.db_config = None
            
            self.db_status_label.setText("연결 상태: 미연결")
            self.db_status_label.setStyleSheet("color: #888888; font-weight: bold;")
            
            self.connect_db_button.setEnabled(True)
            self.disconnect_db_button.setEnabled(False)
            
            print("="*70)
            print("✅ DB 연결 해제 완료")
            print("="*70 + "\n")
            
            QMessageBox.information(self, "DB 연결 해제", "데이터베이스 연결이 해제되었습니다.")
            
        except Exception as e:
            print(f"❌ DB 연결 해제 중 오류: {e}")
            import traceback
            traceback.print_exc()
            
            QMessageBox.warning(
                self, "DB 연결 해제 오류", 
                f"DB 연결 해제 중 오류가 발생했습니다.\n\n{str(e)}"
            )

    def test_db_connection(self):
        """DB 연결 테스트 및 진단"""
        print("\n" + "="*70)
        print("🔍 DB 연결 진단")
        print("="*70)
        
        if not self.db_config:
            print("❌ DB 설정이 없습니다.")
            return False
        
        try:
            conn = mysql.connector.connect(**self.db_config)
            print("✅ DB 연결 성공")
            
            cursor = conn.cursor()
            
            cursor.execute("SHOW TABLES LIKE 'trade_history'")
            table_exists = cursor.fetchone()
            
            if not table_exists:
                print("❌ 'trade_history' 테이블이 존재하지 않습니다.")
                print("   trading_signals.sql 파일을 실행하여 테이블을 생성하세요.")
                cursor.close()
                conn.close()
                return False
            
            print("✅ 'trade_history' 테이블 존재 확인")
            
            cursor.execute("DESCRIBE trade_history")
            columns = cursor.fetchall()
            print("\n📋 테이블 구조:")
            for col in columns:
                print(f"   - {col[0]}: {col[1]}")
            
            cursor.execute("SELECT COUNT(*) FROM trade_history")
            count = cursor.fetchone()[0]
            print(f"\n📊 현재 저장된 거래 내역: {count}개")
            
            cursor.execute("SELECT * FROM trade_history ORDER BY id DESC LIMIT 3")
            recent = cursor.fetchall()
            if recent:
                print("\n📝 최근 거래 내역:")
                for row in recent:
                    print(f"   - ID:{row[0]} {row[2]} {row[3]} {row[4]} {row[5]}@{row[6]}")
            else:
                print("\n📝 아직 거래 내역이 없습니다.")
            
            cursor.close()
            conn.close()
            
            print("\n" + "="*70)
            print("✅ DB 진단 완료 - 정상")
            print("="*70 + "\n")
            return True
            
        except Exception as e:
            print(f"\n❌ DB 진단 실패: {e}")
            import traceback
            traceback.print_exc()
            print("="*70 + "\n")
            return False

    def on_strategy_selected(self, item):
        strategy_name = item.text()
        if item.checkState() == Qt.Checked:
            self.active_strategies.add(strategy_name)
        else:
            self.active_strategies.discard(strategy_name)
        if self.db_watcher:
            self.db_watcher.update_strategies(self.active_strategies)

    def call_latest_signal(self):
        if not self.active_strategies:
            QMessageBox.warning(self, "경고", "먼저 전략을 선택해주세요.")
            return
        if not self.db_connection or not self.db_connection.is_connected():
            QMessageBox.warning(self, "경고", "먼저 데이터베이스에 연결해주세요.")
            return
        
        try:
            connection = mysql.connector.connect(**self.db_config)
            cursor = connection.cursor(dictionary=True, buffered=True)
            strategy_list = list(self.active_strategies)
            placeholders = ','.join(['%s'] * len(strategy_list))
            query = f"SELECT * FROM trading_signals WHERE strategy_name IN ({placeholders}) ORDER BY created_at DESC LIMIT 1"
            cursor.execute(query, strategy_list)
            signal = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if signal:
                print(f"📊 수동 호출: {signal['symbol']} {signal['signal_type']}")
                asyncio.create_task(self.process_manual_signal(signal))
            else:
                QMessageBox.information(self, "정보", "시그널이 없습니다.")
        except Exception as e:
            print(f"❌ 시그널 호출 실패: {e}")

    async def process_manual_signal(self, signal):
        try:
            symbol = signal['symbol']
            signal_type = signal['signal_type']
            confidence = signal.get('confidence', 0)
            signal_time = signal.get('created_at', datetime.now())

            signal_text = f"{symbol} {signal_type} ({confidence:.1%})"
            self.last_signal_label.setText(signal_text)
            self.signal_status_label.setText("📊 수동 호출")
            self.signal_status_label.setStyleSheet("color: #00aaff;")
            
            if isinstance(signal_time, datetime):
                time_str = signal_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                time_str = str(signal_time)
            self.signal_time_label.setText(f"시그널 시간: {time_str}")
            
            self.strategy_signal_received.emit(signal)
        except Exception as e:
            print(f"❌ 수동 시그널 오류: {e}")

    # 2. scan_and_execute_today_signals() 수정 - 간소화
    async def scan_and_execute_today_signals(self, target_date):
        if self.is_processing:
            if not hasattr(self, 'pending_execution'):
                self.pending_execution = False
            self.pending_execution = True
            return

        self.is_processing = True

        try:
            if isinstance(target_date, str):
                date_str = target_date
            else:
                date_str = target_date.strftime('%Y-%m-%d')
            
            print(f"\n{'='*50}")
            print(f"매매 실행: {date_str} ({self.trading_mode})")
            print(f"{'='*50}")

            # DB 조회
            connection = mysql.connector.connect(**self.db_config)
            cursor = connection.cursor(dictionary=True, buffered=True)

            strategy_list = list(self.active_strategies)
            if not strategy_list:
                print("전략 없음")
                cursor.close()
                connection.close()
                return

            placeholders = ','.join(['%s'] * len(strategy_list))
            query = f"""
            SELECT * FROM trading_signals 
            WHERE strategy_name IN ({placeholders})
            AND DATE_FORMAT(created_at, '%Y-%m-%d') = %s
            ORDER BY created_at DESC
            """
            params = strategy_list + [date_str]

            cursor.execute(query, params)
            signals = cursor.fetchall()
            cursor.close()
            connection.close()

            if not signals:
                print("시그널 없음")
                return

            print(f"조회: {len(signals)}개")

            # 심볼별 최신 시그널
            latest_signals = {}
            for signal in signals:
                symbol = signal['symbol']
                if symbol not in latest_signals:
                    latest_signals[symbol] = signal

            # 바이낸스 심볼 변환
            valid_signals = {}
            for symbol, signal in latest_signals.items():
                binance_symbol = get_binance_symbol(symbol)
                if binance_symbol is None:
                    continue
                signal['binance_symbol'] = binance_symbol
                valid_signals[binance_symbol] = signal

            print(f"유효: {len(valid_signals)}개")

            # 보수 모드: 숏 제거
            if self.trading_mode == "CONSERVATIVE":
                short_signals = [sym for sym, sig in valid_signals.items() if sig['signal_type'] == 'SHORT']
                for sym in short_signals:
                    del valid_signals[sym]
                if short_signals:
                    print(f"숏 제거: {len(short_signals)}개")

            # 현재 포지션
            await self.position_manager.get_current_positions()
            current_positions = self.position_manager.active_positions
            print(f"현재: {len(current_positions)}개 포지션")

            # [1단계] 기존 포지션 관리
            print("\n[기존 포지션]")
            for symbol, position_data in list(current_positions.items()):
                if symbol not in valid_signals:
                    continue

                signal = valid_signals[symbol]
                signal_type = signal['signal_type']

                if signal_type == 'HOLD':
                    continue

                # 보수 모드
                if self.trading_mode == "CONSERVATIVE":
                    if position_data['side'] == 'LONG' and signal_type == 'LONG':
                        continue
                    elif position_data['side'] == 'LONG':
                        print(f"{symbol}: 롱 청산")
                        await self.close_position_only(symbol, position_data)
                        continue
                    elif position_data['side'] == 'SHORT':
                        print(f"{symbol}: 숏 청산")
                        await self.close_position_only(symbol, position_data)
                        continue

                # 공격 모드
                if signal_type == position_data['side']:
                    continue

                print(f"{symbol}: {position_data['side']}→{signal_type}")
                await self.close_and_open(symbol, position_data, signal)
                await asyncio.sleep(1)  # 🔥 2초→1초

            # 포지션 재조회
            await self.position_manager.get_current_positions()
            current_positions = self.position_manager.active_positions


            # [2단계] 신규 진입
            print(f"\n[신규 진입]")
            
            if len(current_positions) >= self.position_manager.max_positions:
                print(f"최대 도달 ({len(current_positions)}/{self.position_manager.max_positions})")
                return
            
            available_slots = self.position_manager.max_positions - len(current_positions)
            print(f"가능: {available_slots}개")
            
            # 🔥 신규 진입 대상 시그널 필터링
            new_entry_signals = []
            for symbol, signal in valid_signals.items():
                if symbol in current_positions:
                    continue
                
                signal_type = signal['signal_type']
                
                if signal_type == 'HOLD':
                    continue
                
                # 보수 모드: 숏 제외
                if self.trading_mode == "CONSERVATIVE" and signal_type != 'LONG':
                    continue
                
                # 수동 청산 기록 확인
                if symbol in self.manually_closed_symbols:
                    print(f"{symbol}: 수동 청산 기록 있음 - 재진입 차단")
                    continue
                
                new_entry_signals.append((symbol, signal))
            
            # 🔥 신뢰도 높은 순으로 정렬
            new_entry_signals.sort(key=lambda x: x[1].get('confidence', 0), reverse=True)
            
            print(f"신규 진입 후보: {len(new_entry_signals)}개 (신뢰도순 정렬)")
            
            new_entry_count = 0
            for symbol, signal in new_entry_signals:
                if len(current_positions) >= self.position_manager.max_positions:
                    break
                
                confidence = signal.get('confidence', 0)
                signal_type = signal['signal_type']
                
                print(f"{symbol}: {signal_type} 진입 (신뢰도: {confidence:.1%})")
                
                success = await self.open_position(signal)
                if success:
                    new_entry_count += 1
                    await self.position_manager.get_current_positions()
                    current_positions = self.position_manager.active_positions
                
                await asyncio.sleep(1)
            
            print(f"\n완료: 신규 {new_entry_count}개, 총 {len(current_positions)}개")
            print(f"{'='*50}\n")

        except Exception as e:
            print(f"❌ 오류: {e}")
        finally:
            self.is_processing = False
            
            if hasattr(self, 'pending_execution') and self.pending_execution:
                self.pending_execution = False
                await asyncio.sleep(1)
                await self.scan_and_execute_today_signals(target_date)


    def on_batch_execute_signal(self, message):
        """
        🔥 새로운 메서드: 배치 실행 시그널 처리
        DatabaseWatcher에서 "BATCH_EXECUTE:N" 형태의 메시지를 받으면
        전체 시그널을 다시 조회하여 일괄 처리
        """
        if message.startswith("BATCH_EXECUTE:"):
            count = message.split(":")[1]
            print(f"\n📢 배치 실행 트리거: {count}개 시그널 변경")
            
            target_date = self.target_date.date().toPyDate()
            asyncio.create_task(self.scan_and_execute_today_signals(target_date))

    def start_auto_trading(self):
        """🔥 수정: 초기 스캔 실행 추가"""
        global SYMBOL_PRECISION
        SYMBOL_PRECISION = {}
        print("🔄 정밀도 캐시 초기화")
        
            # 수동 청산 기록 초기화
        if not hasattr(self, 'manually_closed_symbols'):
            self.manually_closed_symbols = set()
        self.manually_closed_symbols.clear()
        print("🧹 수동 청산 기록 초기화")

        if not self.client:
            QMessageBox.warning(self, "경고", "바이낸스에 연결해주세요.")
            return
        if not self.active_strategies:
            QMessageBox.warning(self, "경고", "전략을 선택해주세요.")
            return
        if not self.db_connection or not self.db_connection.is_connected():
            QMessageBox.warning(self, "경고", "DB에 연결해주세요.")
            return

        print("\n" + "="*70)
        print("🚀 자동매매 시작")
        print("="*70)

        max_pos = self.max_positions_spinbox.value()
        self.position_manager.max_positions = max_pos
        scan_interval = self.sql_scan_interval.value()
        target_date = self.target_date.date().toPyDate()

        # 라디오 버튼에서 매매 모드 읽기
        if self.conservative_radio.isChecked():
            self.trading_mode = "CONSERVATIVE"
        else:
            self.trading_mode = "AGGRESSIVE"
        
        print(f"⚙️  매매 모드: {self.trading_mode}")

        # 🔥 수정: 마진 모드 설정 부분 제거 (필요하면 수동으로 설정)
        # 마진 모드는 바이낸스 웹에서 미리 설정하거나, 
        # 각 심볼별로 set_margin_mode() 호출 필요
        
        print("\n" + "="*70)
        print("⚠️  자동매매 주의사항")
        print("="*70)
        print("1. 선택한 날짜의 시그널로 자동 거래합니다")
        print("2. 시그널이 변경되면 포지션을 전환합니다")
        print("3. 최대 포지션 수를 초과하지 않습니다")
        print("4. 실제 자금이 사용되니 신중히 확인하세요")
        print("="*70 + "\n")

        response = QMessageBox.question(
            self,
            "자동매매 시작 확인",
            f"날짜: {target_date}\n모드: {self.trading_mode}\n최대 포지션: {max_pos}개\n\n자동매매를 시작하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if response == QMessageBox.No:
            print("❌ 사용자가 자동매매 시작을 취소했습니다.")
            print("="*70 + "\n")
            return

        print("="*70 + "\n")

        if not self.db_watcher:
            self.db_watcher = DatabaseWatcher(
                self.db_config, 
                self.active_strategies,
                scan_interval=scan_interval,
                target_date=target_date
            )
            self.db_watcher.new_signal_detected.connect(self.on_auto_signal)
            # 🔥 이 줄 추가 - 배치 실행 시그널 연결
            self.db_watcher.status_changed.connect(self.on_batch_execute_signal)
        else:
            self.db_watcher.update_strategies(self.active_strategies)
            self.db_watcher.update_scan_interval(scan_interval)
            self.db_watcher.update_target_date(target_date)

        self.db_watcher.start_watching()

        self.signal_status_label.setText("🤖 자동매매 활성")
        self.signal_status_label.setStyleSheet("color: #00ff00;")
        self.auto_status_label.setText(f"자동매매: 실행 중 ({scan_interval}초 주기)")
        self.start_auto_button.setEnabled(False)
        self.stop_auto_button.setEnabled(True)

        self.trade_setting_widgets.extend([self.sql_scan_interval, self.target_date])
        for widget in self.trade_setting_widgets:
            widget.setEnabled(False)

        print(f"🤖 자동매매 시작")
        print(f"   - 최대 포지션: {max_pos}개")
        print(f"   - SQL 순회 주기: {scan_interval}초")
        print(f"   - 대상 날짜: {target_date}")
        print(f"   - 매매 모드: {self.trading_mode}")

        # 🔥 초기 스캔 실행
        print(f"\n🔍 초기 스캔 실행 중...")
        asyncio.create_task(self.scan_and_execute_today_signals(target_date))


    async def check_available_margin_for_order(self, symbol, quantity, price, leverage):
        """
        🔥 주문 전 실제 사용 가능한 증거금 확인
        
        Returns:
            tuple: (성공 여부, 메시지)
        """
        try:
            account_info = await self.client.get_account_info()
            
            if not account_info:
                return False, "계좌 정보 조회 실패"
            
            available_balance = float(account_info.get('availableBalance', 0))
            total_balance = float(account_info.get('totalWalletBalance', 0))
            total_margin_used = float(account_info.get('totalPositionInitialMargin', 0))
            unrealized_pnl = float(account_info.get('totalUnrealizedProfit', 0))
            
            print(f"\n{'='*70}")
            print(f"💰 증거금 상태 체크: {symbol}")
            print(f"{'='*70}")
            print(f"   총 자산:           {total_balance:.2f} USDT")
            print(f"   사용 가능:         {available_balance:.2f} USDT")
            print(f"   사용 중인 마진:    {total_margin_used:.2f} USDT")
            print(f"   미실현 손익:       {unrealized_pnl:+.2f} USDT")
            
            position_value = quantity * price
            required_margin = position_value / leverage
            estimated_fee = position_value * 0.0004
            total_required = required_margin + estimated_fee
            
            print(f"\n   📊 주문 정보:")
            print(f"   포지션 가치:       {position_value:.2f} USDT")
            print(f"   필요 증거금:       {required_margin:.2f} USDT")
            print(f"   예상 수수료:       {estimated_fee:.4f} USDT")
            print(f"   총 필요 금액:      {total_required:.2f} USDT")
            print(f"{'='*70}\n")
            
            safety_margin = total_required * 1.05
            
            if available_balance < safety_margin:
                shortage = safety_margin - available_balance
                message = (
                    f"❌ 증거금 부족\n\n"
                    f"필요 금액: {safety_margin:.2f} USDT\n"
                    f"사용 가능: {available_balance:.2f} USDT\n"
                    f"부족 금액: {shortage:.2f} USDT\n\n"
                    f"💡 팁:\n"
                    f"- 기존 포지션의 미실현 손실이 있다면 증거금이 줄어듭니다\n"
                    f"- 증거금을 줄이거나 레버리지를 높여보세요\n"
                    f"- 또는 일부 포지션을 청산하여 증거금을 확보하세요"
                )
                print(f"⚠️ {message}")
                return False, message
            
            print(f"✅ 증거금 충분: {available_balance:.2f} USDT >= {safety_margin:.2f} USDT")
            return True, "증거금 충분"
            
        except Exception as e:
            error_msg = f"증거금 체크 중 오류: {str(e)}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return False, error_msg

    async def print_account_status(self):
        """🔥 현재 계좌 상태를 자세히 출력 (디버깅용)"""
        try:
            account_info = await self.client.get_account_info()
            
            if not account_info:
                print("❌ 계좌 정보 조회 실패")
                return
            
            print(f"\n{'='*70}")
            print(f"💼 현재 계좌 상태")
            print(f"{'='*70}")
            print(f"   총 자산:           {float(account_info.get('totalWalletBalance', 0)):.2f} USDT")
            print(f"   사용 가능:         {float(account_info.get('availableBalance', 0)):.2f} USDT")
            print(f"   사용 중인 마진:    {float(account_info.get('totalPositionInitialMargin', 0)):.2f} USDT")
            print(f"   주문 마진:         {float(account_info.get('totalOpenOrderInitialMargin', 0)):.2f} USDT")
            print(f"   미실현 손익:       {float(account_info.get('totalUnrealizedProfit', 0)):+.2f} USDT")
            print(f"   유지 마진:         {float(account_info.get('totalMaintMargin', 0)):.2f} USDT")
            print(f"{'='*70}\n")
            
        except Exception as e:
            print(f"❌ 계좌 상태 출력 오류: {e}")



    async def close_and_open(self, symbol, position_data, new_signal):
        """포지션 청산 후 반대 방향 진입"""
        try:
            print(f"  🔄 포지션 전환: {position_data['side']} → {new_signal['signal_type']}")
            
            # 1. 기존 포지션 청산
            close_success = await self.close_position_only(symbol, position_data)
            
            if not close_success:
                print(f"  ❌ 청산 실패로 전환 중단")
                return False
            
            # 2. 잠시 대기
            await asyncio.sleep(2)
            
            # 3. 새 방향 진입
            open_success = await self.open_position(new_signal)
            
            if open_success:
                print(f"  ✅ 포지션 전환 완료: {symbol} {new_signal['signal_type']}")
                return True
            else:
                print(f"  ❌ 재진입 실패")
                return False
                
        except Exception as e:
            print(f"포지션 전환 실패: {e}")
            return False


    async def check_minimum_quantity_with_signal(self, symbol, quantity, price, signal_type):
        """최소 수량 검증 - 완전 수정"""
        try:
            symbol_info = await self.client.get_symbol_info(symbol)
            
            max_positions = self.max_positions_spinbox.value()
            total_margin = self.usdt_amount.value()
            margin_per_symbol = total_margin / max_positions
            leverage = self.leverage_slider.value()
            
            # 심볼 정보 없을 때
            if not symbol_info:
                print(f"         ⚠️ {symbol} 심볼 정보 없음")
                return False  # 🔥 정보 없으면 무조건 거부
            
            # ✅ 최소 수량 검증
            min_qty = symbol_info.get('minQty', 0)
            if min_qty > 0 and quantity < min_qty:
                print(f"         ❌ {symbol} 최소 수량 미달")
                print(f"            계산: {quantity} < 최소 {min_qty}")
                print(f"            필요 레버리지: 약 {int(leverage * (min_qty/quantity) * 1.1)}x")
                
                self.log_failed_order(
                    symbol=symbol,
                    signal_type=signal_type,
                    reason='최소 수량 미달',
                    details={
                        'price': price,
                        'calculated_quantity': quantity,
                        'min_quantity': min_qty,
                        'min_notional': symbol_info.get('minNotional', 5.0),
                        'total_margin': total_margin,
                        'margin_per_symbol': margin_per_symbol,
                        'leverage': leverage,
                        'max_positions': max_positions
                    }
                )
                return False
            
            # ✅ 최소 금액 검증
            min_notional = symbol_info.get('minNotional', 5.0)
            notional = quantity * price
            
            if notional < min_notional:
                print(f"         ❌ {symbol} 최소 금액 미달")
                print(f"            계산: {notional:.2f} < 최소 {min_notional} USDT")
                
                self.log_failed_order(
                    symbol=symbol,
                    signal_type=signal_type,
                    reason='최소 금액 미달',
                    details={
                        'price': price,
                        'calculated_quantity': quantity,
                        'min_quantity': min_qty,
                        'min_notional': min_notional,
                        'total_margin': total_margin,
                        'margin_per_symbol': margin_per_symbol,
                        'leverage': leverage,
                        'max_positions': max_positions
                    }
                )
                return False
            
            print(f"         ✅ {symbol} 검증 통과: {quantity} ({notional:.2f} USDT)")
            return True
            
        except Exception as e:
            # 🔥🔥🔥 핵심: 오류 시 무조건 False!
            print(f"         ❌ {symbol} 검증 오류: {e}")
            print(f"         ❌ 안전을 위해 주문 거부")
            
            self.log_failed_order(
                symbol=symbol,
                signal_type=signal_type,
                reason=f'검증 오류: {str(e)}',
                details={
                    'price': price,
                    'calculated_quantity': quantity,
                    'error': str(e)
                }
            )
            return False  # ✅✅✅ 반드시 False!


    async def get_fill_info(self, symbol, order_id):
        """주문 체결 정보 조회"""
        try:
            await asyncio.sleep(1)
            
            order_info = await self.client.get_order(symbol, order_id)
            
            if order_info and order_info.get('status') == 'FILLED':
                avg_price = float(order_info.get('avgPrice', 0))
                executed_qty = float(order_info.get('executedQty', 0))
                
                # 수수료 계산 (0.04%)
                commission = (executed_qty * avg_price) * 0.0004
                
                print(f"         📊 실제 체결 정보:")
                print(f"            가격: {avg_price}")
                print(f"            수량: {executed_qty}")
                print(f"            수수료: {commission:.4f} USDT")
                
                return {
                    'avgPrice': avg_price,
                    'executedQty': executed_qty,
                    'commission': commission
                }
            else:
                print(f"         ⚠️ 주문이 아직 체결되지 않음")
                return None
                
        except Exception as e:
            print(f"         ⚠️ 체결 정보 조회 실패: {e}")
            return None

    async def get_contract_size(self, symbol):
        """
        심볼의 계약 크기 반환
        1000SHIBUSDT, 1000PEPEUSDT 등은 1000
        나머지는 1
        """
        if symbol.startswith('1000'):
            return 1000
        return 1

    async def open_position(self, signal):
        """포지션 진입 (레버리지 및 수량 계산 수정)"""
        try:
            symbol = signal.get('binance_symbol', signal['symbol'])
            signal_type = signal['signal_type']
            
            if signal_type == 'HOLD':
                return False
            
            # 🔥 1. 정밀도 및 심볼 정보 로드
            if symbol not in SYMBOL_PRECISION:
                await fetch_symbol_precision(self.client, symbol)
            
            symbol_info = await self.client.get_symbol_info(symbol)
            if not symbol_info:
                print(f"  ❌ {symbol} 심볼 정보 없음 - 스킵")
                return False
            
            min_qty = float(symbol_info.get('minQty', 0))
            min_notional = float(symbol_info.get('minNotional', 5.0))
            
            # 🔥 2. 현재가 조회
            ticker = await self.client.get_ticker(symbol)
            if not ticker or not ticker.get('last'):
                print(f"  ❌ {symbol} 가격 조회 실패 - 스킵")
                return False
            
            current_price = float(ticker['last'])
            
            # 🔥 3. 3등분 금액 계산
            max_positions = self.max_positions_spinbox.value()
            total_margin = self.usdt_amount.value()
            leverage = self.leverage_slider.value()
            
            margin_per_position = total_margin / max_positions
            position_value = margin_per_position * leverage
            
            # 🔥 4. 최소 수량으로 필요한 금액 계산
            min_required_value = min_qty * current_price
            
            print(f"  📊 {symbol} 사전 검증:")
            print(f"     포지션당 금액: {position_value:.2f} USDT")
            print(f"     최소 수량: {min_qty}")
            print(f"     최소 필요 금액: {min_required_value:.2f} USDT")
            
            # 🔥 5. 3등분 금액으로 최소 수량을 못 사면 패스
            if position_value < min_required_value:
                print(f"  ❌ {symbol} 스킵: 3등분 금액({position_value:.2f})으로 최소 수량({min_qty}) 구매 불가")
                print(f"     → 최소 필요: {min_required_value:.2f} USDT")
                return False
            
            # 🔥 6. 최소 notional 체크
            if position_value < min_notional:
                print(f"  ❌ {symbol} 스킵: 3등분 금액({position_value:.2f})이 최소 주문 금액({min_notional}) 미달")
                return False
            
            print(f"  ✅ {symbol} 사전 검증 통과")
            
            ### 여기서부터 기존 로직 (레버리지 설정, 주문 등)
            # 바이낸스가 이미 그 레버리지로 설정되어 있으면 오류 반환
            try:
                leverage_result = await self.client.set_leverage(symbol, leverage)
                print(f"  ✅ 레버리지 {leverage}x 설정 완료")
            except Exception as e:
                if "leverage not modified" in str(e).lower():
                    print(f"  ℹ️ {symbol} 이미 {leverage}x 설정됨")
                else:
                    print(f"  ⚠️ 레버리지 설정 실패: {e}")
                    return False
                
            if not leverage_result:
                print(f"  ❌ 레버리지 설정 실패 - 거래 중단")
                return False  # 🔥 레버리지 설정 실패시 거래 중단
            else:
                print(f"  ✅ 레버리지 {leverage}x 설정 완료")
            
            # 🔥 가격 조회: 바이낸스 API 가격 사용 (필수!)
            ticker = await self.client.get_ticker(symbol)
            if ticker and ticker.get('last'):
                current_price = float(ticker['last'])
                print(f"  📊 바이낸스 현재가: ${current_price}")
            else:
                print(f"  ❌ 가격 조회 실패")
                return False
            
            # 🔥 계약 크기 확인 (1000SHIB, 1000PEPE 등)
            contract_size = 1000 if symbol.startswith('1000') else 1
            
            # 🔥 수량 계산 로직 수정
            max_positions = self.max_positions_spinbox.value()
            total_margin = self.usdt_amount.value()
            
            # ✅ 1. 포지션당 할당 증거금 계산
            margin_per_position = total_margin / max_positions
            
            # ✅ 2. 안전 마진 적용 (97%만 사용)
            safe_margin = margin_per_position * 0.97
            
            # ✅ 3. 실제 포지션 가치 계산 (레버리지 적용)
            target_position_value = safe_margin * leverage
            
            # ✅ 4. 주문 수량 계산
            raw_quantity = target_position_value / current_price
            quantity = adjust_quantity_precision(symbol, raw_quantity)
            
            # ✅ 5. 실제 필요 증거금 재계산 (검증용)
            actual_position_value = quantity * current_price
            required_margin = actual_position_value / leverage
            
            print(f"  💰 계산 상세:")
            if contract_size > 1:
                print(f"     ⚠️ {symbol}은 {contract_size} 단위 심볼")
            print(f"     전체 증거금: {total_margin:.2f} USDT")
            print(f"     최대 포지션 수: {max_positions}개")
            print(f"     포지션당 할당: {margin_per_position:.2f} USDT")
            print(f"     안전 증거금(97%): {safe_margin:.2f} USDT")
            print(f"     레버리지: {leverage}x")
            print(f"     목표 포지션 가치: {target_position_value:.2f} USDT")
            print(f"     계산된 수량: {quantity}")
            print(f"     실제 포지션 가치: {actual_position_value:.2f} USDT")
            print(f"     실제 필요 증거금: {required_margin:.2f} USDT")
            
            # ✅ 6. 증거금 초과 검증
            if required_margin > margin_per_position:
                print(f"  ⚠️ 경고: 필요 증거금({required_margin:.2f})이 할당량({margin_per_position:.2f})을 초과!")
                # 수량 재조정
                safe_quantity = (margin_per_position * 0.95 * leverage) / current_price
                quantity = adjust_quantity_precision(symbol, safe_quantity)
                print(f"  🔧 수량 자동 조정: {quantity}")
            
            # 최소 주문 금액 검증
            min_notional = 5.0  # 바이낸스 선물 최소 주문 금액
            order_value = quantity * current_price
            
            if order_value < min_notional:
                print(f"  ❌ 주문 금액({order_value:.2f} USDT)이 최소 금액({min_notional} USDT) 미만")
                return False
            

            ### 최소주문수량 바로 위에 잇어서 중복임
            # # ✅ 최소 주문 수량/금액 검증 (바이낸스 요구사항 체크)
            # is_valid = await self.check_minimum_quantity_with_signal(
            #     symbol, quantity, current_price, signal_type
            # )
            # if not is_valid:
            #     print(f"  ⚠️ {symbol} 주문 불가: 최소 수량/금액 미달")
            #     print(f"  💡 해결방법: 레버리지 높이기 또는 최대 포지션 수 줄이기")
            #     return False  # 🔥 검증 실패시 다른 종목으로 넘어감
            
            # 주문 실행
            side = 'BUY' if signal_type == 'LONG' else 'SELL'
            
            print(f"  📤 주문 실행: {symbol} {side} {quantity} @ ${current_price}")
            
            result = await self.client.place_order(
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=quantity
            )
            
            if result and 'orderId' in result:
                order_id = result['orderId']
                print(f"  ✅ 주문 성공: ID {order_id}")
                
                # 체결 정보 조회
                await asyncio.sleep(2)
                fill_info = await self.get_fill_info(symbol, order_id)
                
                if fill_info and self.db_manager:
                    # DB 저장
                    trade_data = {
                        'order_id': str(order_id),
                        'symbol': symbol,
                        'side': signal_type,
                        'trade_type': 'ENTRY',
                        'quantity': fill_info['executedQty'],
                        'price': fill_info['avgPrice'],
                        'leverage': leverage,  # 🔥 실제 설정된 레버리지 저장
                        'realized_pnl': 0,
                        'commission': fill_info['commission'],
                        'trade_time': datetime.now()
                    }
                    self.db_manager.save_trade(trade_data)
                
                self.trade_executed.emit()
                await asyncio.sleep(2)
                await self.position_manager.get_current_positions()
                
                return True
            else:
                print(f"  ❌ 주문 실패")
                return False
                
        except Exception as e:
            print(f"❌ 포지션 진입 실패: {e}")
            import traceback
            traceback.print_exc()
            return False


    # 🔥 4. 프로그램 시작 시 캐시 초기화 함수 추가
    def clear_precision_cache():
        """정밀도 캐시 초기화"""
        global SYMBOL_PRECISION
        SYMBOL_PRECISION.clear()
        print("🔄 정밀도 캐시 초기화 완료")

    async def set_margin_mode(self, symbol, margin_type):
        """마진 모드 설정 (CROSS/ISOLATED)"""
        if not self.client:
            return
        
        try:
            params = {
                'symbol': symbol,
                'marginType': margin_type
            }
            
            result = await self.client._make_request(
                "POST", 
                "/fapi/v1/marginType", 
                params, 
                signed=True
            )
            
            print(f"✅ {symbol} 마진 모드: {margin_type}")
            return result
            
        except Exception as e:
            error_str = str(e)
            if "No need to change margin type" in error_str or "-4046" in error_str:
                print(f"ℹ️ {symbol}는 이미 {margin_type} 모드입니다.")
            else:
                print(f"⚠️ 마진 모드 설정 실패: {e}")
                raise

    def stop_auto_trading(self):
        """자동매매 중지"""
        print("\n" + "="*70)
        print("🛑 자동매매 중지")
        print("="*70)
        
        if self.db_watcher:
            self.db_watcher.stop_watching()
            print("   ✅ DB Watcher 중지 완료")
        
        self.signal_status_label.setText("🔴 중지")
        self.signal_status_label.setStyleSheet("color: #ff4444;")
        self.auto_status_label.setText("자동매매: 중지")
        
        self.start_auto_button.setEnabled(True)
        self.stop_auto_button.setEnabled(False)
        
        # 위젯 활성화
        if hasattr(self, 'trade_setting_widgets'):
            all_widgets = self.trade_setting_widgets + [self.sql_scan_interval, self.target_date]
        else:
            all_widgets = [self.sql_scan_interval, self.target_date]
        
        for widget in all_widgets:
            try:
                widget.setEnabled(True)
            except:
                pass
        
        # ✅ usdt_radio가 있을 때만 호출 (TradingWidget용)
        if hasattr(self, 'on_amount_type_changed') and hasattr(self, 'usdt_radio'):
            self.on_amount_type_changed()
        
        print("="*70)
        print("✅ 자동매매 중지 완료")
        print("="*70 + "\n")

    def on_auto_signal(self, signal):
        """자동 시그널 처리 (포지션 변경 감지)"""
        if not self.is_processing:
            signal_time = signal.get('created_at', datetime.now())
            if isinstance(signal_time, datetime):
                time_str = signal_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                time_str = str(signal_time)
            self.signal_time_label.setText(f"시그널 시간: {time_str}")
            
            asyncio.create_task(self.process_realtime_signal(signal))
    
    async def process_realtime_signal(self, signal):
        """실시간 시그널 처리"""
        if self.is_processing:
            return
        
        self.is_processing = True
        
        try:
            symbol = signal['symbol']
            signal_type = signal['signal_type']
            
            binance_symbol = get_binance_symbol(symbol)
            if binance_symbol is None:
                print(f"   {symbol}: 바이낸스 미지원")
                return
            
            if binance_symbol != symbol:
                print(f"   {symbol}→{binance_symbol} 변환")
                signal['symbol'] = binance_symbol
                symbol = binance_symbol
            
            print(f"\n🚨 실시간: {symbol} {signal_type}")
            
            # 🔥🔥🔥 보수 모드: 숏 시그널 차단
            if self.trading_mode == "CONSERVATIVE" and signal_type == 'SHORT':
                print(f"   🚫 {symbol}: 숏 시그널 무시 (보수 모드)")
                return
            
            if signal_type == 'HOLD':
                print(f"   {symbol}: HOLD - 포지션 유지")
                return
            
            await self.position_manager.get_current_positions()
            current_positions = self.position_manager.active_positions
            
            if symbol in current_positions:
                existing = current_positions[symbol]
                
                if existing['side'] == signal_type:
                    print(f"   {symbol}: {signal_type} - 동일 방향 유지")
                    return
                
                # 보수 모드: 롱→숏 전환 차단
                if self.trading_mode == "CONSERVATIVE":
                    print(f"   {symbol}: 청산만 (보수 모드)")
                    await self.close_position_only(symbol, existing)
                else:
                    print(f"   {symbol}: {existing['side']}→{signal_type} 전환")
                    await self.close_and_open(symbol, existing, signal)
            else:
                if len(current_positions) >= self.position_manager.max_positions:
                    print(f"   {symbol}: 최대 포지션 도달")
                    return
                
                # 🔥 보수 모드: 롱만 진입
                if self.trading_mode == "CONSERVATIVE" and signal_type != 'LONG':
                    print(f"   {symbol}: 숏 진입 차단 (보수 모드)")
                    return
                
                print(f"   {symbol}: {signal_type} 신규 진입")
                await self.open_position(signal)
            
            await self.update_position_display()
            
        except Exception as e:
            print(f"❌ 실시간 시그널 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_processing = False

    def closeEvent(self, event):
        """위젯 종료 시 정리 작업"""
        print("\n" + "="*70)
        print("🔄 Strategy Widget 종료 중...")
        print("="*70)
        
        try:
            if self.db_watcher and self.db_watcher.is_watching:
                print("   🛑 자동매매 중지 중...")
                self.stop_auto_trading()
            
            if self.db_connection:
                try:
                    if self.db_connection.is_connected():
                        self.db_connection.close()
                        print("   ✅ DB 연결 종료")
                except Exception as e:
                    print(f"   ⚠️ DB 연결 종료 오류 (무시): {e}")
            
            print("="*70)
            print("✅ Strategy Widget 종료 완료")
            print("="*70 + "\n")
            
        except Exception as e:
            print(f"❌ 종료 중 오류: {e}")
        
        event.accept()