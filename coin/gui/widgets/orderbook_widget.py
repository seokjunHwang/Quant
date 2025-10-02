from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QGroupBox, QComboBox, QSpinBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
import asyncio

from config.symbol_config import get_symbol_list

class OrderbookWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.client = None
        self.current_symbol = "BTCUSDT"
        self.update_timer = None
        self.ticker_timer = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 심볼 선택 및 설정 섹션
        control_group = QGroupBox("호가창 설정")
        control_layout = QHBoxLayout(control_group)
        
        # 심볼 선택
        control_layout.addWidget(QLabel("심볼:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(get_symbol_list('top100'))
        
        self.symbol_combo.currentTextChanged.connect(self.on_symbol_changed)
        control_layout.addWidget(self.symbol_combo)
        
        # 호가 깊이 설정
        control_layout.addWidget(QLabel("깊이:"))
        self.depth_spinbox = QSpinBox()
        self.depth_spinbox.setRange(5, 20)
        self.depth_spinbox.setValue(10)
        self.depth_spinbox.setSuffix("단계")
        control_layout.addWidget(self.depth_spinbox)
        
        # 업데이트 간격 설정
        control_layout.addWidget(QLabel("업데이트:"))
        self.update_interval = QSpinBox()
        self.update_interval.setRange(1, 10)
        self.update_interval.setValue(2)
        self.update_interval.setSuffix("초")
        self.update_interval.valueChanged.connect(self.restart_timer)
        control_layout.addWidget(self.update_interval)
        
        # 새로고침 버튼
        self.refresh_button = QPushButton("새로고침")
        self.refresh_button.clicked.connect(self.update_orderbook)
        control_layout.addWidget(self.refresh_button)
        
        layout.addWidget(control_group)
        
        # 현재가 정보 섹션
        price_group = QGroupBox("현재가 정보")
        price_layout = QHBoxLayout(price_group)
        
        self.current_price_label = QLabel("현재가: -")
        self.price_change_label = QLabel("24h 변동: -")
        self.volume_label = QLabel("24h 거래량: -")
        
        font = QFont("맑은 고딕", 11, QFont.Bold)
        for label in [self.current_price_label, self.price_change_label, self.volume_label]:
            label.setFont(font)
            price_layout.addWidget(label)
            
        layout.addWidget(price_group)
        
        # 호가창 테이블 섹션
        orderbook_group = QGroupBox("호가창")
        orderbook_layout = QVBoxLayout(orderbook_group)
        
        # 매도 호가 테이블 (ASK)
        ask_label = QLabel("매도 호가 (ASK)")
        ask_label.setStyleSheet("color: #ff4444; font-weight: bold; font-size: 12px;")
        orderbook_layout.addWidget(ask_label)
        
        self.ask_table = QTableWidget()
        self.ask_table.setColumnCount(3)
        self.ask_table.setHorizontalHeaderLabels(["가격(USDT)", "수량", "누적"])
        self.ask_table.setMaximumHeight(300)
        
        # 테이블 헤더 설정
        ask_header = self.ask_table.horizontalHeader()
        ask_header.setSectionResizeMode(QHeaderView.Stretch)
        self.ask_table.verticalHeader().setVisible(False)
        
        orderbook_layout.addWidget(self.ask_table)
        
        # 현재가 표시 (중간)
        self.spread_label = QLabel("스프레드: -")
        self.spread_label.setAlignment(Qt.AlignCenter)
        self.spread_label.setStyleSheet("""
            background-color: #444; 
            color: white; 
            font-weight: bold; 
            font-size: 14px; 
            padding: 8px; 
            border: 1px solid #666;
        """)
        orderbook_layout.addWidget(self.spread_label)
        
        # 매수 호가 테이블 (BID)
        bid_label = QLabel("매수 호가 (BID)")
        bid_label.setStyleSheet("color: #00ff00; font-weight: bold; font-size: 12px;")
        orderbook_layout.addWidget(bid_label)
        
        self.bid_table = QTableWidget()
        self.bid_table.setColumnCount(3)
        self.bid_table.setHorizontalHeaderLabels(["가격(USDT)", "수량", "누적"])
        self.bid_table.setMaximumHeight(300)
        
        # 테이블 헤더 설정
        bid_header = self.bid_table.horizontalHeader()
        bid_header.setSectionResizeMode(QHeaderView.Stretch)
        self.bid_table.verticalHeader().setVisible(False)
        
        orderbook_layout.addWidget(self.bid_table)
        layout.addWidget(orderbook_group)

        # 🔥 업데이트 간격 설정 (기본값 1초로 변경)
        control_layout.addWidget(QLabel("업데이트:"))
        self.update_interval = QSpinBox()
        self.update_interval.setRange(1, 10)
        self.update_interval.setValue(1)  # 🔥 기본값 1초
        self.update_interval.setSuffix("초")
        self.update_interval.valueChanged.connect(self.restart_timer)
        control_layout.addWidget(self.update_interval)

        # 테이블 스타일 적용
        table_style = """
            QTableWidget {
                background-color: #2b2b2b;
                color: white;
                gridline-color: #555;
                border: 1px solid #555;
                selection-background-color: transparent;
            }
            QTableWidget::item {
                padding: 6px;
                border-bottom: 1px solid #444;
            }
            QHeaderView::section {
                background-color: #444;
                color: white;
                padding: 6px;
                border: 1px solid #555;
                font-weight: bold;
            }
        """
        
        self.ask_table.setStyleSheet(table_style)
        self.bid_table.setStyleSheet(table_style)
        
        # 전체 위젯 스타일
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555;
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
            QComboBox, QSpinBox {
                background-color: #555;
                border: 1px solid #777;
                border-radius: 3px;
                padding: 5px;
                color: white;
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
        """)
        
    def set_client(self, client):
        """바이낸스 클라이언트 설정"""
        self.client = client
        self.start_auto_update()
        
    def start_auto_update(self):
        """자동 업데이트 시작"""
        if self.update_timer:
            self.update_timer.stop()
        if self.ticker_timer:
            self.ticker_timer.stop()
            
        # 즉시 한 번 업데이트
        self.update_orderbook()
        self.update_ticker_info()
        
        # 🔥 호가창 타이머 시작 (1초 기본)
        interval = self.update_interval.value() * 1000
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_orderbook)
        self.update_timer.start(interval)
        
        # 🔥 티커 정보는 3초마다 (기존 5초에서 단축)
        self.ticker_timer = QTimer()
        self.ticker_timer.timeout.connect(self.update_ticker_info)
        self.ticker_timer.start(3000)
        
        print(f"✅ 호가창 자동 업데이트: {self.update_interval.value()}초마다")



    def restart_timer(self):
        """타이머 재시작"""
        if self.client:
            self.start_auto_update()
            
    def on_symbol_changed(self):
        """심볼 변경 시 호출"""
        self.current_symbol = self.symbol_combo.currentText()
        if self.client:
            self.update_orderbook()
            self.update_ticker_info()
            
    def update_orderbook(self):
        """호가창 업데이트"""
        if self.client:
            asyncio.create_task(self._update_orderbook_async())
            
    async def _update_orderbook_async(self):
        """비동기 호가창 업데이트"""
        try:
            depth = self.depth_spinbox.value()
            orderbook = await self.client.get_orderbook(self.current_symbol, depth)
            
            if orderbook and 'bids' in orderbook and 'asks' in orderbook:
                await self.populate_orderbook_tables(orderbook)
                
        except Exception as e:
            print(f"호가창 업데이트 오류: {e}")
            
    async def populate_orderbook_tables(self, orderbook):
        """호가창 테이블 채우기"""
        try:
            bids = orderbook['bids'][:self.depth_spinbox.value()]
            asks = orderbook['asks'][:self.depth_spinbox.value()]
            
            # ASK 테이블 채우기 (높은 가격부터)
            asks.reverse()  # 높은 가격이 위로 오도록
            self.ask_table.setRowCount(len(asks))
            
            ask_cumulative = 0
            for row, (price, quantity) in enumerate(asks):
                price = float(price)
                quantity = float(quantity)
                ask_cumulative += quantity
                
                price_item = QTableWidgetItem(f"{price:.4f}")
                quantity_item = QTableWidgetItem(f"{quantity:.6f}")
                cumulative_item = QTableWidgetItem(f"{ask_cumulative:.6f}")
                
                # 매도 호가는 빨간색
                for item in [price_item, quantity_item, cumulative_item]:
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setForeground(QColor('#ff4444'))
                    
                self.ask_table.setItem(row, 0, price_item)
                self.ask_table.setItem(row, 1, quantity_item)
                self.ask_table.setItem(row, 2, cumulative_item)
            
            # BID 테이블 채우기 (높은 가격부터)
            self.bid_table.setRowCount(len(bids))
            
            bid_cumulative = 0
            for row, (price, quantity) in enumerate(bids):
                price = float(price)
                quantity = float(quantity)
                bid_cumulative += quantity
                
                price_item = QTableWidgetItem(f"{price:.4f}")
                quantity_item = QTableWidgetItem(f"{quantity:.6f}")
                cumulative_item = QTableWidgetItem(f"{bid_cumulative:.6f}")
                
                # 매수 호가는 초록색
                for item in [price_item, quantity_item, cumulative_item]:
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setForeground(QColor('#00ff00'))
                    
                self.bid_table.setItem(row, 0, price_item)
                self.bid_table.setItem(row, 1, quantity_item)
                self.bid_table.setItem(row, 2, cumulative_item)
            
            # 스프레드 계산 및 표시
            if bids and asks:
                best_bid = float(bids[0][0])
                best_ask = float(asks[-1][0])  # reverse 했으므로 마지막이 최저가
                spread = best_ask - best_bid
                spread_percent = (spread / best_ask) * 100
                
                self.spread_label.setText(
                    f"스프레드: {spread:.4f} USDT ({spread_percent:.3f}%)"
                )
                
        except Exception as e:
            print(f"호가창 테이블 업데이트 오류: {e}")
            
    def update_ticker_info(self):
        """티커 정보 업데이트"""
        if self.client:
            asyncio.create_task(self._update_ticker_info_async())
            
    async def _update_ticker_info_async(self):
        """비동기 티커 정보 업데이트"""
        try:
            ticker = await self.client.get_24hr_ticker(self.current_symbol)
            
            if ticker:
                # 현재가
                current_price = float(ticker.get('lastPrice', 0))
                self.current_price_label.setText(f"현재가: {current_price:.4f} USDT")
                
                # 24시간 변동
                price_change = float(ticker.get('priceChange', 0))
                price_change_percent = float(ticker.get('priceChangePercent', 0))
                
                if price_change > 0:
                    change_color = "color: #00ff00;"
                    change_text = f"24h 변동: +{price_change:.4f} (+{price_change_percent:.2f}%)"
                elif price_change < 0:
                    change_color = "color: #ff4444;"
                    change_text = f"24h 변동: {price_change:.4f} ({price_change_percent:.2f}%)"
                else:
                    change_color = "color: white;"
                    change_text = f"24h 변동: {price_change:.4f} ({price_change_percent:.2f}%)"
                    
                self.price_change_label.setText(change_text)
                self.price_change_label.setStyleSheet(change_color)
                
                # 24시간 거래량
                volume = float(ticker.get('volume', 0))
                quote_volume = float(ticker.get('quoteVolume', 0))
                self.volume_label.setText(f"24h 거래량: {quote_volume:,.0f} USDT")
                
        except Exception as e:
            print(f"티커 정보 업데이트 오류: {e}")
            
    def closeEvent(self, event):
        """위젯 종료 시 타이머 정리"""
        if self.update_timer:
            self.update_timer.stop()
        if hasattr(self, 'ticker_timer') and self.ticker_timer:
            self.ticker_timer.stop()
        event.accept()