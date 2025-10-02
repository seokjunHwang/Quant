from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QGroupBox, QComboBox, 
                             QSpinBox, QDoubleSpinBox, QMessageBox, QCheckBox, QSlider)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import asyncio

from config.symbol_config import get_symbol_list
from datetime import datetime
from widgets.database_manager import DatabaseManager  # 또는 strategy_widget에서 복사

# 🔥 바이낸스 심볼 정밀도 설정 (완전 보완)
SYMBOL_PRECISION = {
    'BTCUSDT': {'price': 1, 'quantity': 3},
    'ETHUSDT': {'price': 2, 'quantity': 3},
    'BNBUSDT': {'price': 2, 'quantity': 2},
    'ADAUSDT': {'price': 4, 'quantity': 0},    # ADA는 정수
    'DOGEUSDT': {'price': 5, 'quantity': 0},   # DOGE는 정수
    'XRPUSDT': {'price': 4, 'quantity': 1},
    'DOTUSDT': {'price': 3, 'quantity': 1},
    'LINKUSDT': {'price': 3, 'quantity': 1},
    'LTCUSDT': {'price': 2, 'quantity': 2},
    'BCHUSDT': {'price': 2, 'quantity': 3},
    'AVAXUSDT': {'price': 3, 'quantity': 1},
    'SOLUSDT': {'price': 3, 'quantity': 1},
    'MATICUSDT': {'price': 4, 'quantity': 0}, # MATIC은 정수
    'ATOMUSDT': {'price': 3, 'quantity': 1},
    'UNIUSDT': {'price': 3, 'quantity': 1},
    
    # 🔥 중요 심볼들 추가
    '1000SHIBUSDT': {'price': 6, 'quantity': 0},  # SHIB는 정수
    'TRXUSDT': {'price': 5, 'quantity': 0},       # TRX는 정수
    'PEPEUSDT': {'price': 7, 'quantity': 0},      # PEPE는 정수
    '1000FLOKIUSDT': {'price': 5, 'quantity': 0}, # FLOKI는 정수
    'SANDUSDT': {'price': 4, 'quantity': 0},      # SAND는 정수
    'MANAUSDT': {'price': 4, 'quantity': 0},      # MANA는 정수
    'APTUSDT': {'price': 3, 'quantity': 1},
    'OPUSDT': {'price': 4, 'quantity': 1},
    'ARBUSDT': {'price': 4, 'quantity': 1},
    'SUIUSDT': {'price': 4, 'quantity': 1},
}


def adjust_quantity_precision(symbol, quantity):
    """심볼에 맞게 수량 정밀도 조정 + 최소값 보장"""
    if symbol in SYMBOL_PRECISION:
        precision = SYMBOL_PRECISION[symbol]['quantity']
        adjusted = round(quantity, precision)
        
        # 최소값 보장
        min_val = 1 if precision == 0 else 10 ** (-precision)
        if adjusted < min_val:
            print(f"⚠️ {symbol}: 최소 수량 조정 {adjusted} -> {min_val}")
            adjusted = min_val
            
        return adjusted
    else:
        # 기본값: 소수점 3자리, 최소 0.001
        return max(round(quantity, 3), 0.001)


def adjust_price_precision(symbol, price):
    """심볼에 맞게 가격 정밀도 조정"""
    if symbol in SYMBOL_PRECISION:
        precision = SYMBOL_PRECISION[symbol]['price']
        return round(price, precision)
    else:
        return round(price, 4)  # 기본값


class TradingWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.client = None
        self.current_price = 0
        self.db_manager = None  # 🔥 추가
        self.init_ui()
        
    def init_ui(self):
        self.setMaximumWidth(420)
        layout = QVBoxLayout(self)
        
        # ==================== 거래 설정 섹션 (개선) ====================
        trading_group = QGroupBox("수동 거래")
        trading_layout = QVBoxLayout(trading_group)
        
        # 1. 심볼 선택
        symbol_layout = QHBoxLayout()
        symbol_layout.addWidget(QLabel("심볼:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(get_symbol_list('top100'))
        self.symbol_combo.currentTextChanged.connect(self.on_symbol_changed)
        symbol_layout.addWidget(self.symbol_combo)

        # 현재가 표시
        self.current_price_label = QLabel("현재가: -")
        font = QFont("맑은 고딕", 11, QFont.Bold)
        self.current_price_label.setFont(font)
        symbol_layout.addWidget(self.current_price_label)
        
        # 정밀도 정보 표시
        self.precision_info_label = QLabel("정밀도: -")
        self.precision_info_label.setStyleSheet("color: #888; font-size: 10px;")
        symbol_layout.addWidget(self.precision_info_label)
        
        trading_layout.addLayout(symbol_layout)
        
        # 2. 주문 타입 (MARKET/LIMIT)
        order_type_layout = QHBoxLayout()
        order_type_layout.addWidget(QLabel("주문 타입:"))
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(["MARKET", "LIMIT"])
        self.order_type_combo.currentTextChanged.connect(self.on_order_type_changed)
        order_type_layout.addWidget(self.order_type_combo)
        trading_layout.addLayout(order_type_layout)
        
        # 3. 가격 설정 (LIMIT 주문용)
        price_layout = QHBoxLayout()
        price_layout.addWidget(QLabel("가격:"))
        
        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("가격 입력 (USDT)")
        self.price_input.setText("0")
        self.price_input.setEnabled(False)
        self.price_input.textChanged.connect(self.validate_price_input)
        price_layout.addWidget(self.price_input)
        
        # 현재가 적용 버튼
        self.apply_current_price_btn = QPushButton("현재가 적용")
        self.apply_current_price_btn.clicked.connect(self.apply_current_price)
        self.apply_current_price_btn.setEnabled(False)
        self.apply_current_price_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:disabled { background-color: #6c757d; }
        """)
        price_layout.addWidget(self.apply_current_price_btn)
        trading_layout.addLayout(price_layout)
        
        # 가격 조정 버튼들 (LIMIT 주문시)
        price_adjust_layout = QHBoxLayout()
        
        self.price_minus_btn = QPushButton("-1%")
        self.price_minus_btn.clicked.connect(lambda: self.adjust_price(-0.01))
        self.price_minus_btn.setEnabled(False)
        
        self.price_minus_01_btn = QPushButton("-0.1%")
        self.price_minus_01_btn.clicked.connect(lambda: self.adjust_price(-0.001))
        self.price_minus_01_btn.setEnabled(False)
        
        self.price_plus_01_btn = QPushButton("+0.1%")
        self.price_plus_01_btn.clicked.connect(lambda: self.adjust_price(0.001))
        self.price_plus_01_btn.setEnabled(False)
        
        self.price_plus_btn = QPushButton("+1%")
        self.price_plus_btn.clicked.connect(lambda: self.adjust_price(0.01))
        self.price_plus_btn.setEnabled(False)
        
        adjust_btn_style = """
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 10px;
                min-width: 40px;
            }
            QPushButton:hover { background-color: #5a6268; }
            QPushButton:disabled { background-color: #495057; color: #6c757d; }
        """
        
        for btn in [self.price_minus_btn, self.price_minus_01_btn, 
                   self.price_plus_01_btn, self.price_plus_btn]:
            btn.setStyleSheet(adjust_btn_style)
            price_adjust_layout.addWidget(btn)
        
        trading_layout.addLayout(price_adjust_layout)
        
        # 4. 🔥 마진 모드 선택 (CROSS/ISOLATED)
        margin_mode_layout = QHBoxLayout()
        margin_mode_layout.addWidget(QLabel("마진 모드:"))
        self.margin_mode_combo = QComboBox()
        self.margin_mode_combo.addItems(["CROSS", "ISOLATED"])
        self.margin_mode_combo.setToolTip("CROSS: 전체 잔고 공유 / ISOLATED: 격리 마진")
        margin_mode_layout.addWidget(self.margin_mode_combo)
        trading_layout.addLayout(margin_mode_layout)
        
        # 5. 🔥 증거금(USDT) 입력 - strategy_widget처럼
        usdt_layout = QHBoxLayout()
        usdt_layout.addWidget(QLabel("증거금(USDT):"))
        self.usdt_amount_input = QDoubleSpinBox()
        self.usdt_amount_input.setRange(10.0, 100000.0)
        self.usdt_amount_input.setValue(100.0)
        self.usdt_amount_input.setDecimals(2)
        self.usdt_amount_input.setSuffix(" USDT")
        self.usdt_amount_input.valueChanged.connect(self.update_position_value_display)
        usdt_layout.addWidget(self.usdt_amount_input)
        trading_layout.addLayout(usdt_layout)
        
        # 6. 🔥 레버리지 슬라이더 - strategy_widget처럼
        leverage_layout = QHBoxLayout()
        leverage_layout.addWidget(QLabel("레버리지:"))
        self.leverage_slider = QSlider(Qt.Horizontal)
        self.leverage_slider.setMinimum(1)
        self.leverage_slider.setMaximum(50)
        self.leverage_slider.setValue(10)
        self.leverage_slider.setTickPosition(QSlider.TicksBelow)
        self.leverage_slider.setTickInterval(5)
        self.leverage_slider.valueChanged.connect(self.update_position_value_display)
        
        self.leverage_label = QLabel(f"{self.leverage_slider.value()}x")
        self.leverage_label.setMinimumWidth(40)
        self.leverage_label.setStyleSheet("font-weight: bold; color: #00d4aa;")
        
        leverage_layout.addWidget(self.leverage_slider)
        leverage_layout.addWidget(self.leverage_label)
        trading_layout.addLayout(leverage_layout)
        
        # 7. 🔥 총 포지션 가치 표시
        self.total_value_label = QLabel("총 포지션 가치: 1,000.00 USDT")
        self.total_value_label.setStyleSheet("""
            color: #00d4aa; 
            font-weight: bold; 
            padding: 8px; 
            background-color: #3c3c3c; 
            border-radius: 5px;
            font-size: 12px;
        """)
        self.total_value_label.setAlignment(Qt.AlignCenter)
        trading_layout.addWidget(self.total_value_label)
        
        # 8. 🔥 예상 수량 미리보기
        self.quantity_preview_label = QLabel("예상 수량: -")
        self.quantity_preview_label.setStyleSheet("""
            color: #ffffff; 
            font-weight: bold; 
            padding: 5px; 
            background-color: #444; 
            border-radius: 3px;
            font-size: 11px;
        """)
        self.quantity_preview_label.setAlignment(Qt.AlignCenter)
        trading_layout.addWidget(self.quantity_preview_label)
        
        layout.addWidget(trading_group)
        
        # ==================== 주문 버튼 섹션 ====================
        button_group = QGroupBox("주문 실행")
        button_layout = QVBoxLayout(button_group)
        
        order_buttons_layout = QHBoxLayout()
        
        self.buy_button = QPushButton("매수 (LONG)")
        self.buy_button.clicked.connect(lambda: self.place_order("BUY"))
        self.buy_button.setStyleSheet("""
            QPushButton {
                background-color: #00aa00;
                color: white;
                font-weight: bold;
                padding: 10px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #008800; }
        """)
        
        self.sell_button = QPushButton("매도 (SHORT)")
        self.sell_button.clicked.connect(lambda: self.place_order("SELL"))
        self.sell_button.setStyleSheet("""
            QPushButton {
                background-color: #cc0000;
                color: white;
                font-weight: bold;
                padding: 10px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #aa0000; }
        """)
        
        order_buttons_layout.addWidget(self.buy_button)
        order_buttons_layout.addWidget(self.sell_button)
        button_layout.addLayout(order_buttons_layout)
        
        self.cancel_all_button = QPushButton("모든 주문 취소")
        self.cancel_all_button.clicked.connect(self.cancel_all_orders)
        button_layout.addWidget(self.cancel_all_button)
        
        layout.addWidget(button_group)
        
        self.apply_styles()
        
    def apply_styles(self):
        """위젯 스타일 적용"""
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #666;
                border-radius: 5px;
                margin-top: 10px;
                background-color: #3c3c3c;
                color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #555;
                border: 1px solid #777;
                border-radius: 3px;
                padding: 5px;
                color: white;
            }
            QLineEdit {
                background-color: #555;
                border: 1px solid #777;
                border-radius: 3px;
                padding: 5px;
                color: white;
                font-weight: bold;
            }
            QLineEdit:focus {
                border: 2px solid #0078d4;
                background-color: #666;
            }
            QPushButton {
                background-color: #0078d4;
                border: none;
                border-radius: 3px;
                padding: 8px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QLabel {
                color: white;
                padding: 2px;
            }
            QCheckBox {
                color: white;
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
    def set_client(self, client):
        """바이낸스 클라이언트 설정"""
        self.client = client
        # 클라이언트 설정 후 지연 실행으로 현재가 업데이트 (태스크 충돌 방지)
        QTimer.singleShot(500, lambda: asyncio.create_task(self.update_current_price()))
        
        # 주기적 현재가 업데이트 (30초마다)
        self.price_timer = QTimer()
        self.price_timer.timeout.connect(lambda: asyncio.create_task(self.update_current_price()))
        self.price_timer.start(30000)
        
        # 심볼 변경시 정밀도 정보 업데이트
        self.update_precision_info()

    def set_db_config(self, db_config):
        """
        DB 설정 받기 (Strategy Widget에서 호출)
        
        Args:
            db_config: DB 연결 설정 딕셔너리
        """
        if db_config:
            self.db_manager = DatabaseManager(db_config)
            print("✅ Trading Widget: DB 매니저 설정 완료")

    def set_db_manager(self, db_manager):
        """
        DB 매니저 직접 받기
        
        Args:
            db_manager: DatabaseManager 인스턴스
        """
        self.db_manager = db_manager
        print("✅ Trading Widget: DB 매니저 직접 연결됨")

    def on_symbol_changed(self):
        """심볼 변경 시 현재가 업데이트"""
        if self.client:
            asyncio.create_task(self.update_current_price())
        self.update_precision_info()
        self.update_position_value_display()
            
    def update_precision_info(self):
        """현재 선택된 심볼의 정밀도 정보 표시"""
        symbol = self.symbol_combo.currentText()
        if symbol in SYMBOL_PRECISION:
            price_precision = SYMBOL_PRECISION[symbol]['price']
            qty_precision = SYMBOL_PRECISION[symbol]['quantity']
            
            if qty_precision == 0:
                qty_text = "정수만"
            else:
                qty_text = f"소수점 {qty_precision}자리"
                
            self.precision_info_label.setText(f"정밀도: 가격 {price_precision}자리, 수량 {qty_text}")
        else:
            self.precision_info_label.setText("정밀도: 기본값 (가격 4자리, 수량 3자리)")
            
    def on_order_type_changed(self):
        """주문 타입 변경 시 가격 입력 활성화/비활성화"""
        is_limit = self.order_type_combo.currentText() == "LIMIT"
        
        # 가격 관련 컨트롤들 활성화/비활성화
        self.price_input.setEnabled(is_limit)
        self.apply_current_price_btn.setEnabled(is_limit)
        self.price_minus_btn.setEnabled(is_limit)
        self.price_plus_btn.setEnabled(is_limit)
        self.price_minus_01_btn.setEnabled(is_limit)
        self.price_plus_01_btn.setEnabled(is_limit)
        
        if is_limit:
            # 지정가 주문일 때 현재가로 초기값 설정
            if self.current_price > 0:
                symbol = self.symbol_combo.currentText()
                adjusted_price = adjust_price_precision(symbol, self.current_price)
                self.price_input.setText(f"{adjusted_price}")
            else:
                # 현재가가 없으면 즉시 조회
                asyncio.create_task(self.update_current_price())
        else:
            # 시장가 주문일 때는 0으로 설정
            self.price_input.setText("0")
    
    def update_position_value_display(self):
        """총 포지션 가치 및 레버리지 라벨 업데이트"""
        try:
            leverage = self.leverage_slider.value()
            margin = self.usdt_amount_input.value()
            
            # 레버리지 라벨 업데이트
            self.leverage_label.setText(f"{leverage}x")
            
            # 총 포지션 가치 = 증거금 × 레버리지
            total_value = margin * leverage
            self.total_value_label.setText(f"총 포지션 가치: {total_value:,.2f} USDT")
            
            # 예상 수량도 함께 업데이트
            self.update_quantity_preview()
            
        except Exception as e:
            print(f"포지션 가치 업데이트 오류: {e}")
        
    def update_quantity_preview(self):
        """예상 수량 미리보기 업데이트"""
        try:
            symbol = self.symbol_combo.currentText()
            
            # 증거금 기반 계산
            usdt_amount = self.usdt_amount_input.value()
            leverage = self.leverage_slider.value()
            
            if self.current_price > 0:
                raw_qty = (usdt_amount * leverage) / self.current_price
                adjusted_qty = adjust_quantity_precision(symbol, raw_qty)
                self.quantity_preview_label.setText(f"예상 수량: {adjusted_qty}")
            else:
                self.quantity_preview_label.setText("예상 수량: 현재가 조회 중...")
                    
        except Exception as e:
            self.quantity_preview_label.setText("예상 수량: 계산 오류")
            print(f"수량 미리보기 오류: {e}")
        
    def validate_price_input(self):
        """가격 입력 검증"""
        try:
            text = self.price_input.text()
            if text and text != "0":
                price = float(text)
                if price < 0:
                    self.price_input.setText("0")
        except ValueError:
            # 숫자가 아닌 경우 이전 값 유지
            pass
            
    def apply_current_price(self):
        """현재가를 가격 입력란에 적용"""
        if self.current_price > 0:
            symbol = self.symbol_combo.currentText()
            adjusted_price = adjust_price_precision(symbol, self.current_price)
            self.price_input.setText(f"{adjusted_price}")
        else:
            asyncio.create_task(self.update_current_price())
            
    def adjust_price(self, percentage):
        """가격 조정 (퍼센트)"""
        try:
            current_text = self.price_input.text()
            symbol = self.symbol_combo.currentText()
            
            if current_text and current_text != "0":
                current_price = float(current_text)
                new_price = current_price * (1 + percentage)
                adjusted_price = adjust_price_precision(symbol, new_price)
                self.price_input.setText(f"{adjusted_price}")
            elif self.current_price > 0:
                # 입력값이 없으면 현재가 기준으로 조정
                new_price = self.current_price * (1 + percentage)
                adjusted_price = adjust_price_precision(symbol, new_price)
                self.price_input.setText(f"{adjusted_price}")
        except ValueError:
            pass
        
    async def update_current_price(self):
        """현재가 업데이트"""
        if not self.client:
            return
            
        try:
            symbol = self.symbol_combo.currentText()
            
            # 직접 바이낸스 API 사용
            ticker = await self.client.get_ticker_price(symbol)
            print(f"현재가 조회: {symbol} -> {ticker}")
            
            if ticker and 'price' in ticker:
                self.current_price = float(ticker['price'])
                adjusted_price = adjust_price_precision(symbol, self.current_price)
                self.current_price_label.setText(f"현재가: {adjusted_price} USDT")
                
                # 지정가 주문인 경우 가격 자동 설정 (입력값이 0일 때만)
                if (self.order_type_combo.currentText() == "LIMIT" and 
                    (self.price_input.text() == "0" or not self.price_input.text())):
                    self.price_input.setText(f"{adjusted_price}")
                    
                # 수량 미리보기 업데이트
                self.update_quantity_preview()
            else:
                print(f"현재가 정보가 없습니다: {ticker}")
                    
        except Exception as e:
            print(f"현재가 업데이트 오류: {e}")
            import traceback
            traceback.print_exc()
            
    def get_price_value(self):
        """가격 입력값 가져오기"""
        try:
            text = self.price_input.text()
            if text and text != "0":
                return float(text)
            return 0
        except ValueError:
            return 0
            
    def calculate_quantity(self):
        """주문 수량 계산 (증거금 기반으로 통일)"""
        symbol = self.symbol_combo.currentText()
        
        # 증거금 × 레버리지 기반 계산
        usdt_amount = self.usdt_amount_input.value()
        leverage = self.leverage_slider.value()
        
        if self.order_type_combo.currentText() == "MARKET":
            price = self.current_price
        else:
            price = self.get_price_value()
            
        if price > 0:
            raw_quantity = self.client.calculate_quantity(usdt_amount, price, leverage)
            # 🔥 정밀도 적용
            adjusted_quantity = adjust_quantity_precision(symbol, raw_quantity)
            print(f"수량 계산: {raw_quantity:.6f} -> {adjusted_quantity}")
            return adjusted_quantity
            
        return 0
        
    def place_order(self, side):
        """주문 실행"""
        asyncio.create_task(self._place_order_async(side))
        
    async def _place_order_async(self, side):
        """비동기 주문 실행 (마진 모드 설정 추가)"""
        if not self.client:
            QMessageBox.warning(self, "오류", "API가 연결되지 않았습니다.")
            return
            
        # 버튼 비활성화 (중복 클릭 방지)
        self.buy_button.setEnabled(False)
        self.sell_button.setEnabled(False)
        
        try:
            symbol = self.symbol_combo.currentText()
            order_type = self.order_type_combo.currentText()
            quantity = self.calculate_quantity()
            leverage = self.leverage_slider.value()
            margin_mode = self.margin_mode_combo.currentText()
            
            print(f"주문 정보: {symbol} {side} {order_type} 수량:{quantity} 레버리지:{leverage}x 마진:{margin_mode}")
            
            if quantity <= 0:
                QMessageBox.warning(self, "오류", "유효한 수량을 입력해주세요.")
                return
            
            # 마진 모드 설정
            try:
                await self.set_margin_mode(symbol, margin_mode)
                print(f"마진 모드 설정 완료: {margin_mode}")
            except Exception as me:
                print(f"⚠️ 마진 모드 설정 실패: {me} (계속 진행)")
                
            # 레버리지 설정
            try:
                await self.client.set_leverage(symbol, leverage)
                print(f"레버리지 설정 완료: {leverage}x")
            except Exception as le:
                print(f"레버리지 설정 오류: {le}")
            
            # 주문 실행
            if order_type == "MARKET":
                print(f"시장가 주문 실행: {symbol} {side} {quantity}")
                result = await self.client.place_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity
                )
            else:  # LIMIT
                price = self.get_price_value()
                if price <= 0:
                    QMessageBox.warning(self, "오류", "유효한 가격을 입력해주세요.")
                    return
                    
                adjusted_price = adjust_price_precision(symbol, price)
                print(f"지정가 주문 실행: {symbol} {side} {quantity} @ {adjusted_price}")
                
                result = await self.client.place_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    price=adjusted_price
                )
                
            print(f"주문 결과: {result}")
            
            if result and 'orderId' in result:
                side_text = "매수" if side == "BUY" else "매도"
                
                if order_type == "LIMIT":
                    adjusted_price = adjust_price_precision(symbol, self.get_price_value())
                    price_text = f"@ {adjusted_price}"
                    actual_price = adjusted_price
                else:
                    price_text = "(시장가)"
                    actual_price = float(result.get('avgPrice', self.current_price))
                
                # 🔥 DB에 거래 저장
                if self.db_manager:
                    try:
                        self.db_manager.save_trade({
                            'order_id': result['orderId'],
                            'symbol': symbol,
                            'side': 'LONG' if side == 'BUY' else 'SHORT',
                            'trade_type': 'ENTRY',  # 수동 거래는 ENTRY로
                            'quantity': quantity,
                            'price': actual_price,
                            'realized_pnl': 0.0,
                            'commission': 0.0,
                            'trade_time': datetime.now()
                        })
                        print(f"✅ 거래 내역 DB 저장 완료")
                    except Exception as db_e:
                        print(f"⚠️ DB 저장 실패 (주문은 성공): {db_e}")
                else:
                    print("⚠️ DB 매니저가 없어 거래 내역 저장 안됨")
                
                QMessageBox.information(
                    self, 
                    "주문 완료", 
                    f"{side_text} 주문이 완료되었습니다.\n\n"
                    f"주문ID: {result['orderId']}\n"
                    f"심볼: {symbol}\n"
                    f"수량: {quantity}\n"
                    f"가격: {price_text}\n"
                    f"타입: {order_type}\n"
                    f"마진 모드: {margin_mode}\n"
                    f"레버리지: {leverage}x"
                )
            else:
                print(f"⚠️ 주문 실패 또는 알 수 없는 응답: {result}")
                QMessageBox.warning(self, "주문 실패", f"주문이 실패했거나 서버로부터 알 수 없는 응답을 받았습니다.\n\n응답: {result}")
                
        except Exception as e:
            print(f"주문 실행 오류: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "오류", f"주문 중 오류 발생: {str(e)}")
        
        finally:
            # 버튼 다시 활성화
            self.buy_button.setEnabled(True)
            self.sell_button.setEnabled(True)
    
    async def set_margin_mode(self, symbol, margin_type):
        """
        마진 모드 설정 (CROSS/ISOLATED)
        
        Args:
            symbol: 심볼 (예: 'BTCUSDT')
            margin_type: 'CROSS' 또는 'ISOLATED'
        """
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
            # 이미 설정된 모드면 에러 무시
            error_str = str(e)
            if "No need to change margin type" in error_str or "-4046" in error_str:
                print(f"ℹ️ {symbol}는 이미 {margin_type} 모드입니다.")
            else:
                print(f"⚠️ 마진 모드 설정 실패: {e}")
                raise
            
    def cancel_all_orders(self):
        """모든 주문 취소"""
        asyncio.create_task(self._cancel_all_orders_async())
        
    async def _cancel_all_orders_async(self):
        """모든 주문 취소 (비동기)"""
        if not self.client:
            return
            
        try:
            # 전체 미체결 주문 조회
            open_orders = await self.client.get_open_orders()
            
            if not open_orders:
                QMessageBox.information(self, "알림", "취소할 주문이 없습니다.")
                return
                
            cancelled_count = 0
            failed_count = 0
            
            print(f"취소할 주문 수: {len(open_orders)}")
            
            for order in open_orders:
                try:
                    symbol = order.get('symbol', '')
                    order_id = str(order.get('orderId', ''))
                    
                    print(f"주문 취소 시도: {symbol} - {order_id}")
                    
                    result = await self.client.cancel_order(symbol, order_id)
                    
                    if result:
                        cancelled_count += 1
                        print(f"주문 취소 성공: {order_id}")
                    else:
                        failed_count += 1
                        print(f"주문 취소 실패: {order_id}")
                        
                except Exception as e:
                    print(f"개별 주문 취소 오류 ({order_id}): {e}")
                    failed_count += 1
                    
            # 결과 메시지
            message = f"취소 완료: {cancelled_count}개"
            if failed_count > 0:
                message += f"\n실패: {failed_count}개"
                
            QMessageBox.information(self, "취소 결과", message)
            
        except Exception as e:
            print(f"전체 주문 취소 오류: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "오류", f"주문 취소 중 오류: {str(e)}")

    # 🔥 추가 유틸리티 메서드들
    def get_symbol_info_display(self):
        """현재 심볼의 정보를 표시용으로 가져오기"""
        symbol = self.symbol_combo.currentText()
        if symbol in SYMBOL_PRECISION:
            return SYMBOL_PRECISION[symbol]
        return {'price': 4, 'quantity': 3}  # 기본값

    def validate_order_inputs(self):
        """주문 입력값 유효성 검사"""
        errors = []
        
        symbol = self.symbol_combo.currentText()
        
        # 수량 검증
        quantity = self.calculate_quantity()
        if quantity <= 0:
            errors.append("수량이 0보다 커야 합니다")
        
        # 가격 검증 (지정가 주문시)
        if self.order_type_combo.currentText() == "LIMIT":
            price = self.get_price_value()
            if price <= 0:
                errors.append("가격이 0보다 커야 합니다")
        
        # 심볼별 최소값 검증
        if symbol in SYMBOL_PRECISION:
            qty_precision = SYMBOL_PRECISION[symbol]['quantity']
            if qty_precision == 0 and quantity != int(quantity):
                errors.append(f"{symbol}은 정수 수량만 가능합니다")
        
        return errors

    def show_order_preview(self, side):
        """주문 미리보기 다이얼로그"""
        errors = self.validate_order_inputs()
        if errors:
            QMessageBox.warning(self, "입력 오류", "\n".join(errors))
            return False
        
        symbol = self.symbol_combo.currentText()
        order_type = self.order_type_combo.currentText()
        quantity = self.calculate_quantity()
        leverage = self.leverage_slider.value()
        margin_mode = self.margin_mode_combo.currentText()
        
        preview_text = f"주문 미리보기\n\n"
        preview_text += f"심볼: {symbol}\n"
        preview_text += f"방향: {'매수 (LONG)' if side == 'BUY' else '매도 (SHORT)'}\n"
        preview_text += f"타입: {order_type}\n"
        preview_text += f"수량: {quantity}\n"
        
        if order_type == "LIMIT":
            price = adjust_price_precision(symbol, self.get_price_value())
            preview_text += f"가격: {price} USDT\n"
            total_value = quantity * price
        else:
            preview_text += f"가격: 시장가\n"
            total_value = quantity * self.current_price if self.current_price > 0 else 0
            
        preview_text += f"레버리지: {leverage}x\n"
        preview_text += f"마진 모드: {margin_mode}\n"
        preview_text += f"예상 거래금액: {total_value:.2f} USDT\n"
        
        margin = self.usdt_amount_input.value()
        preview_text += f"사용 증거금: {margin:.2f} USDT\n"
        
        reply = QMessageBox.question(
            self, "주문 확인", 
            preview_text + "\n주문을 실행하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        return reply == QMessageBox.Yes

    def closeEvent(self, event):
        """위젯 종료 시 타이머 정리"""
        if hasattr(self, 'price_timer') and self.price_timer:
            self.price_timer.stop()
        event.accept()