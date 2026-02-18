from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QGroupBox, QMessageBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
from datetime import datetime
import asyncio

class OrderQueueWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.client = None
        self.update_timer = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 주문 요약 섹션
        summary_group = QGroupBox("주문 요약")
        summary_layout = QVBoxLayout(summary_group)
        
        # 요약 정보
        summary_info_layout = QHBoxLayout()
        
        self.total_orders_label = QLabel("총 주문: 0건")
        self.buy_orders_label = QLabel("매수: 0건")
        self.sell_orders_label = QLabel("매도: 0건")
        
        font = QFont("맑은 고딕", 10, QFont.Bold)
        for label in [self.total_orders_label, self.buy_orders_label, self.sell_orders_label]:
            label.setFont(font)
            summary_info_layout.addWidget(label)
            
        summary_layout.addLayout(summary_info_layout)
        
        # 전체 주문 취소 버튼
        self.cancel_all_button = QPushButton("모든 주문 취소")
        self.cancel_all_button.clicked.connect(self.cancel_all_orders)
        self.cancel_all_button.setStyleSheet("""
            QPushButton {
                background-color: #cc0000;
                color: white;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #aa0000;
            }
        """)
        summary_layout.addWidget(self.cancel_all_button)
        
        layout.addWidget(summary_group)
        
        # 주문 테이블 섹션
        table_group = QGroupBox("대기 중인 주문")
        table_layout = QVBoxLayout(table_group)
        
        # 주문 테이블
        self.order_table = QTableWidget()
        self.order_table.setColumnCount(8)
        self.order_table.setHorizontalHeaderLabels([
            "주문시간", "심볼", "방향", "타입", "수량", "가격", "상태", "액션"
        ])
        
        # 테이블 헤더 설정
        header = self.order_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 주문시간
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 심볼
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 방향
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 타입
        header.setSectionResizeMode(4, QHeaderView.Stretch)          # 수량
        header.setSectionResizeMode(5, QHeaderView.Stretch)          # 가격
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 상태
        header.setSectionResizeMode(7, QHeaderView.Fixed)            # 액션
        
        self.order_table.setColumnWidth(7, 80)  # 액션 열 너비
        
        # 테이블 스타일
        self.order_table.setAlternatingRowColors(True)
        self.order_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.order_table.setStyleSheet("""
            QTableWidget {
                background-color: #2b2b2b;
                color: white;
                gridline-color: #555;
                border: 1px solid #555;
                alternate-background-color: #353535;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #444;
                color: white;
                background-color: transparent;
            }
            QTableWidget::item:alternate {
                background-color: #353535;
            }
            QTableWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QTableWidget::item:hover {
                background-color: #404040;
            }
            QHeaderView::section {
                background-color: #444;
                color: white;
                padding: 8px;
                border: 1px solid #555;
                font-weight: bold;
            }
        """)
        
        table_layout.addWidget(self.order_table)
        layout.addWidget(table_group)
        
        # # 새로고침 버튼
        # self.refresh_button = QPushButton("새로고침")
        # self.refresh_button.clicked.connect(self.update_orders)
        # layout.addWidget(self.refresh_button)
        
        # 🔥 버튼 레이아웃
        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton("🔄 주문 조회")
        self.refresh_button.clicked.connect(self.manual_refresh)
        button_layout.addWidget(self.refresh_button)
        
        # 자동 업데이트 상태 표시
        self.auto_update_label = QLabel("⏱️ 자동 업데이트: 5분마다 (거래 시 즉시)")
        self.auto_update_label.setStyleSheet("color: #888; font-size: 10px;")
        button_layout.addWidget(self.auto_update_label)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)

        # 스타일 적용
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
        
    def manual_refresh(self):
        """수동 주문 조회"""
        if self.client:
            print("🔄 수동 주문 조회 실행...")
            self.update_orders()
    
    def set_client(self, client):
        """바이낸스 클라이언트 설정"""
        self.client = client
        
        # 즉시 주문 업데이트
        self.update_orders()
        
        # 🔥 자동 업데이트 타이머 시작 (5분마다)
        if self.update_timer:
            self.update_timer.stop()
            
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_orders)
        self.update_timer.start(300000)  # 5분 = 300,000ms
        
        print("✅ 주문대기열 자동 업데이트: 5분마다")
        
    def update_orders(self):
        """주문 정보 업데이트"""
        if self.client:
            asyncio.create_task(self._update_orders_async())
            
    async def _update_orders_async(self):
        """비동기 주문 업데이트 - 직접 바이낸스 API"""
        try:
            # print("=== 직접 바이낸스 미체결 주문 조회 ===")
            orders = await self.client.get_open_orders()
            # print(f"미체결 주문 수: {len(orders) if orders else 0}")
            
            if orders is not None:
                await self.populate_order_table(orders)
            else:
                print("미체결 주문 조회 실패")
                
        except Exception as e:
            print(f"주문 업데이트 오류: {e}")
            import traceback
            traceback.print_exc()
            
    async def populate_order_table(self, orders):
        """주문 테이블 채우기 - 바이낸스 원본 데이터 사용"""
        try:
            # print(f"=== 주문 테이블 업데이트: {len(orders)}개 ===")
            
            self.order_table.setRowCount(len(orders))
            
            buy_count = 0
            sell_count = 0
            
            for row, order in enumerate(orders):
                print(f"주문 {row}: {order}")
                
                # 바이낸스 원본 API 필드 직접 사용
                order_id = str(order.get('orderId', ''))
                symbol = order.get('symbol', '')
                side = order.get('side', '').upper()
                order_type = order.get('type', '').upper()
                orig_qty = float(order.get('origQty', 0))
                price = float(order.get('price', 0)) if order.get('price') else 0
                status = order.get('status', '').upper()
                time_stamp = int(order.get('time', 0))
                
                # 시간 변환
                if time_stamp:
                    order_time = datetime.fromtimestamp(time_stamp / 1000).strftime('%H:%M:%S')
                else:
                    order_time = "-"
                
                # 방향별 카운트
                if side == "BUY":
                    buy_count += 1
                else:
                    sell_count += 1
                
                # 테이블 아이템 설정 (바이낸스 원본 데이터 직접 사용)
                items = [
                    QTableWidgetItem(order_time),
                    QTableWidgetItem(symbol),
                    QTableWidgetItem(side),
                    QTableWidgetItem(order_type),
                    QTableWidgetItem(f"{orig_qty:.6f}"),
                    QTableWidgetItem(f"{price:.4f}" if price > 0 else "시장가"),
                    QTableWidgetItem(status),
                ]
                
                # 각 열에 아이템 설정
                for col, item in enumerate(items):
                    item.setTextAlignment(Qt.AlignCenter)
                    
                    # 색상 설정
                    if col == 2:  # 방향 열
                        if side == "BUY":
                            item.setForeground(QColor('#00ff00'))
                        else:
                            item.setForeground(QColor('#ff4444'))
                    elif col == 6:  # 상태 열
                        if status == "NEW":
                            item.setForeground(QColor('#ffaa00'))
                        
                    self.order_table.setItem(row, col, item)
                
                # 취소 버튼 추가
                cancel_button = QPushButton("취소")
                cancel_button.setFixedSize(70, 25)
                cancel_button.setStyleSheet("""
                    QPushButton {
                        background-color: #cc0000;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        font-size: 10px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #aa0000;
                    }
                """)
                cancel_button.clicked.connect(
                    lambda checked, oid=order_id, sym=symbol: self.cancel_order(sym, oid)
                )
                
                # 버튼을 중앙 정렬
                button_widget = QWidget()
                button_layout = QHBoxLayout(button_widget)
                button_layout.setContentsMargins(5, 2, 5, 2)
                button_layout.addWidget(cancel_button, 0, Qt.AlignCenter)
                
                self.order_table.setCellWidget(row, 7, button_widget)
                self.order_table.setRowHeight(row, 35)
            
            # 요약 정보 업데이트
            total_count = len(orders)
            self.total_orders_label.setText(f"총 주문: {total_count}건")
            self.buy_orders_label.setText(f"매수: {buy_count}건")
            self.sell_orders_label.setText(f"매도: {sell_count}건")
            
            print(f"주문 테이블 업데이트 완료: 총 {total_count}건 (매수: {buy_count}, 매도: {sell_count})")
            
        except Exception as e:
            print(f"주문 테이블 업데이트 오류: {e}")
            import traceback
            traceback.print_exc()
            
    def cancel_order(self, symbol, order_id):
        """개별 주문 취소"""
        reply = QMessageBox.question(
            self, 
            "주문 취소", 
            f"{symbol} 주문을 취소하시겠습니까?\n주문ID: {order_id}",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            asyncio.create_task(self._cancel_order_async(symbol, order_id))
            
    async def _cancel_order_async(self, symbol, order_id):
        """비동기 주문 취소 - 직접 바이낸스 API"""
        try:
            print(f"=== 주문 취소: {symbol} {order_id} ===")
            result = await self.client.cancel_order(symbol, order_id)
            print(f"주문 취소 결과: {result}")
            
            if result and 'orderId' in result:
                QMessageBox.information(self, "취소 완료", f"주문이 취소되었습니다.")
                self.update_orders()
            else:
                QMessageBox.warning(self, "오류", "주문 취소에 실패했습니다.")
                
        except Exception as e:
            print(f"주문 취소 오류: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "오류", f"주문 취소 중 오류: {str(e)}")
            
    def cancel_all_orders(self):
        """모든 주문 취소"""
        reply = QMessageBox.question(
            self, 
            "모든 주문 취소", 
            "모든 미체결 주문을 취소하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            asyncio.create_task(self._cancel_all_orders_async())
            
    async def _cancel_all_orders_async(self):
        """모든 주문 비동기 취소"""
        try:
            print("=== 모든 주문 취소 시작 ===")
            orders = await self.client.get_open_orders()
            
            if not orders:
                QMessageBox.information(self, "알림", "취소할 주문이 없습니다.")
                return
                
            cancelled_count = 0
            failed_count = 0
            
            for order in orders:
                try:
                    symbol = order.get('symbol', '')
                    order_id = str(order.get('orderId', ''))
                    
                    result = await self.client.cancel_order(symbol, order_id)
                    
                    if result and 'orderId' in result:
                        cancelled_count += 1
                        print(f"주문 취소 성공: {order_id}")
                    else:
                        failed_count += 1
                        print(f"주문 취소 실패: {order_id}")
                        
                except Exception as e:
                    print(f"주문 취소 오류 ({order_id}): {e}")
                    failed_count += 1
                    
            # 결과 메시지
            message = f"취소 완료: {cancelled_count}건"
            if failed_count > 0:
                message += f"\n실패: {failed_count}건"
                
            QMessageBox.information(self, "취소 결과", message)
            self.update_orders()
            
        except Exception as e:
            print(f"전체 주문 취소 오류: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "오류", f"전체 주문 취소 중 오류: {str(e)}")
            
    def closeEvent(self, event):
        """위젯 종료 시 타이머 정리"""
        if self.update_timer:
            self.update_timer.stop()
        event.accept()