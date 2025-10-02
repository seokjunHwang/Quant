# trade_history_widget.py - 페이지네이션 기능 추가

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QComboBox, QDateEdit,
                             QCheckBox, QMessageBox, QFileDialog)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QColor
from datetime import datetime, timedelta
import mysql.connector

class TradeHistoryWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.client = None
        self.db_config = None
        
        # 🔥 페이지네이션 변수
        self.current_page = 1
        self.items_per_page = 20
        self.max_items = 200  # 최대 200개 (10페이지)
        self.total_count = 0
        self.all_trades = []  # 조회된 전체 데이터 (최대 200개)
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 조회 조건 섹션
        filter_group = QGroupBox("조회 조건")
        filter_layout = QVBoxLayout(filter_group)
        row1_layout = QHBoxLayout()
        row1_layout.addWidget(QLabel("심볼:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItem("전체")
        # self.symbol_combo.addItems(get_symbol_list('top100'))  # 필요시 추가

        row1_layout.addWidget(self.symbol_combo)
        row1_layout.addWidget(QLabel("시작일:"))
        self.start_date = QDateEdit()
        # 🔥 오늘 날짜로 설정
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        row1_layout.addWidget(self.start_date)
        row1_layout.addWidget(QLabel("종료일:"))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        row1_layout.addWidget(self.end_date)
        filter_layout.addLayout(row1_layout)
        
        row2_layout = QHBoxLayout()
        row2_layout.addWidget(QLabel("방향:"))
        self.side_combo = QComboBox()
        self.side_combo.addItems(["전체", "BUY", "SELL"])
        row2_layout.addWidget(self.side_combo)
        self.auto_refresh_checkbox = QCheckBox("자동 새로고침")
        row2_layout.addWidget(self.auto_refresh_checkbox)
        self.search_button = QPushButton("조회")
        self.search_button.clicked.connect(self.load_trade_history)
        row2_layout.addWidget(self.search_button)
        self.export_button = QPushButton("엑셀 내보내기")
        self.export_button.clicked.connect(self.export_to_excel)
        row2_layout.addWidget(self.export_button)
        filter_layout.addLayout(row2_layout)
        layout.addWidget(filter_group)

        # 손익 요약 섹션
        summary_group = QGroupBox("손익 요약")
        summary_layout = QHBoxLayout(summary_group)
        self.total_trades_label = QLabel("총 거래: 0건")
        self.total_volume_label = QLabel("총 거래량: 0 USDT")
        self.total_fee_label = QLabel("총 수수료: 0 USDT")
        self.total_pnl_label = QLabel("총 손익: 0 USDT")
        font = QFont("맑은 고딕", 10, QFont.Bold)
        for label in [self.total_trades_label, self.total_volume_label,
                     self.total_fee_label, self.total_pnl_label]:
            label.setFont(font)
            summary_layout.addWidget(label)
        layout.addWidget(summary_group)

        # 🔥 페이지네이션 컨트롤
        pagination_layout = QHBoxLayout()
        self.page_info_label = QLabel("페이지: 0 / 0")
        self.prev_button = QPushButton("◀ 이전")
        self.prev_button.clicked.connect(self.prev_page)
        self.next_button = QPushButton("다음 ▶")
        self.next_button.clicked.connect(self.next_page)
        
        pagination_layout.addWidget(self.page_info_label)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addWidget(self.next_button)
        layout.addLayout(pagination_layout)

        # 거래내역 테이블 섹션
        table_group = QGroupBox("거래 내역")
        table_layout = QVBoxLayout(table_group)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(11)
        self.history_table.setHorizontalHeaderLabels([
            "시간", "심볼", "방향", "타입", "수량", "가격", 
            "레버리지", "거래금액", "수수료", "실현손익", "순수익%"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table_layout.addWidget(self.history_table)
        layout.addWidget(table_group)

        self.apply_styles()

    def apply_styles(self):
        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: white; }
            QGroupBox { 
                font-weight: bold; border: 2px solid #555; border-radius: 5px; 
                margin-top: 10px; background-color: #3c3c3c; color: white; 
            }
            QGroupBox::title { 
                subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px; 
            }
            QComboBox, QDateEdit { 
                background-color: #555; border: 1px solid #777; border-radius: 3px; 
                padding: 5px; color: white; 
            }
            QPushButton { 
                background-color: #0078d4; border: none; border-radius: 3px; 
                padding: 8px; color: white; font-weight: bold; 
            }
            QPushButton:hover { background-color: #106ebe; }
            QPushButton:disabled { background-color: #555; color: #888; }
            QLabel { color: white; padding: 2px; }
            QCheckBox { color: white; }
            QTableWidget { 
                background-color: #2b2b2b; color: white; gridline-color: #555; 
                border: 1px solid #555; alternate-background-color: #353535; 
            }
            QTableWidget::item { padding: 8px; border-bottom: 1px solid #444; }
            QTableWidget::item:selected { background-color: #0078d4; }
            QHeaderView::section { 
                background-color: #444; color: white; padding: 8px; 
                border: 1px solid #555; font-weight: bold; 
            }
        """)

    def set_db_config(self, db_config):
        self.db_config = db_config
        self.load_trade_history()

    def load_trade_history(self):
        """거래 내역 조회 시작"""
        if self.db_config:
            self.current_page = 1  # 조회 시 페이지 초기화
            self._load_trade_history_from_db()
        else:
            QMessageBox.warning(self, "오류", "먼저 DB에 연결해주세요.")

    def _load_trade_history_from_db(self):
        try:
            connection = mysql.connector.connect(**self.db_config)
            cursor = connection.cursor(dictionary=True)

            # 🔥 1단계: WHERE 조건 구성
            where_conditions = "WHERE 1=1"
            params = []

            symbol = self.symbol_combo.currentText()
            if symbol != "전체":
                where_conditions += " AND symbol = %s"
                params.append(symbol)

            side = self.side_combo.currentText()
            if side != "전체":
                side_param = 'LONG' if side == 'BUY' else 'SHORT'
                where_conditions += " AND side = %s"
                params.append(side_param)

            start_date = self.start_date.date().toPyDate()
            end_date = self.end_date.date().toPyDate() + timedelta(days=1)
            
            where_conditions += " AND trade_time >= %s AND trade_time < %s"
            params.extend([start_date, end_date])
            
            # 🔥 2단계: 전체 건수 및 통계 조회
            count_query = f"""
                SELECT 
                    COUNT(*) as total_count,
                    COALESCE(SUM(quantity * price), 0) as total_volume,
                    COALESCE(SUM(commission), 0) as total_fee,
                    COALESCE(SUM(realized_pnl), 0) as total_pnl
                FROM trade_history
                {where_conditions}
            """
            cursor.execute(count_query, params)
            stats = cursor.fetchone()
            self.total_count = stats['total_count']
            
            # 🔥 3단계: 화면 표시용 데이터 조회 (최대 100개만)
            data_query = f"""
                SELECT * FROM trade_history 
                {where_conditions} 
                ORDER BY trade_time DESC 
                LIMIT {self.max_items}
            """
            cursor.execute(data_query, params)
            self.all_trades = cursor.fetchall()

            cursor.close()
            connection.close()
            
            print(f"DB에서 전체 {self.total_count}건 중 {len(self.all_trades)}개 로드 (최대 200개)")
            
            # 통계 업데이트
            self.update_summary(stats)
            
            # 첫 페이지 표시
            self.display_current_page()

        except Exception as e:
            print(f"DB 거래내역 로드 오류: {e}")
            QMessageBox.critical(self, "DB 오류", f"거래내역을 불러오는 중 오류가 발생했습니다:\n{e}")
            self.history_table.setRowCount(0)

    def display_current_page(self):
        """현재 페이지 데이터 표시"""
        try:
            # 페이지 범위 계산
            start_idx = (self.current_page - 1) * self.items_per_page
            end_idx = min(start_idx + self.items_per_page, len(self.all_trades))
            
            # 현재 페이지 데이터 추출
            page_trades = self.all_trades[start_idx:end_idx]
            
            # 테이블 업데이트
            self.populate_history_table(page_trades)
            
            # 페이지 정보 업데이트
            total_pages = (len(self.all_trades) + self.items_per_page - 1) // self.items_per_page
            self.page_info_label.setText(f"페이지: {self.current_page} / {total_pages} (총 {len(self.all_trades)}개 중 {start_idx + 1}-{end_idx})")
            
            # 버튼 활성화/비활성화
            self.prev_button.setEnabled(self.current_page > 1)
            self.next_button.setEnabled(end_idx < len(self.all_trades))
            
        except Exception as e:
            print(f"페이지 표시 오류: {e}")

    def prev_page(self):
        """이전 페이지"""
        if self.current_page > 1:
            self.current_page -= 1
            self.display_current_page()

    def next_page(self):
        """다음 페이지"""
        total_pages = (len(self.all_trades) + self.items_per_page - 1) // self.items_per_page
        if self.current_page < total_pages:
            self.current_page += 1
            self.display_current_page()

    def populate_history_table(self, trades):
        """거래내역 테이블 채우기"""
        try:
            self.history_table.setRowCount(len(trades))

            for row, trade in enumerate(trades):
                try:
                    # 시간 변환
                    trade_time = trade.get('trade_time')
                    if trade_time and isinstance(trade_time, datetime):
                        time_str = trade_time.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        time_str = str(trade_time) if trade_time else 'N/A'
                    
                    # 데이터 추출
                    symbol = str(trade.get('symbol', 'N/A'))
                    side = str(trade.get('side', 'N/A'))
                    trade_type = str(trade.get('trade_type', 'N/A'))
                    
                    try:
                        quantity = float(trade.get('quantity') or 0)
                        price = float(trade.get('price') or 0)
                        leverage = int(trade.get('leverage') or 1)
                        commission = float(trade.get('commission') or 0)
                        realized_pnl = float(trade.get('realized_pnl') or 0)
                    except (ValueError, TypeError):
                        quantity = price = commission = realized_pnl = 0.0
                        leverage = 1
                    
                    entry_value = quantity * price
                    net_profit_percent = (realized_pnl / entry_value * 100) if entry_value > 0 else 0
                    
                    # 테이블 아이템 생성
                    items = [
                        QTableWidgetItem(time_str),
                        QTableWidgetItem(symbol),
                        QTableWidgetItem(side),
                        QTableWidgetItem(trade_type),
                        QTableWidgetItem(f"{quantity:.4f}"),
                        QTableWidgetItem(f"{price:.2f}"),
                        QTableWidgetItem(f"{leverage}x"),
                        QTableWidgetItem(f"{entry_value:.2f}"),
                        QTableWidgetItem(f"{commission:.6f}"),
                        QTableWidgetItem(f"{realized_pnl:.2f}"),
                        QTableWidgetItem(f"{net_profit_percent:.2f}%")
                    ]
                    
                    # 색상 적용
                    if side == 'LONG':
                        items[2].setForeground(QColor("#00ff00"))
                    elif side == 'SHORT':
                        items[2].setForeground(QColor("#ff4444"))
                    
                    if realized_pnl > 0:
                        items[9].setForeground(QColor("#00ff00"))
                        items[10].setForeground(QColor("#00ff00"))
                    elif realized_pnl < 0:
                        items[9].setForeground(QColor("#ff4444"))
                        items[10].setForeground(QColor("#ff4444"))
                    
                    # 테이블에 추가
                    for col, item in enumerate(items):
                        item.setTextAlignment(Qt.AlignCenter)
                        self.history_table.setItem(row, col, item)

                except Exception as e:
                    print(f"행 {row} 처리 오류: {e}")
                    continue

        except Exception as e:
            print(f"테이블 업데이트 오류: {e}")

    def update_summary(self, stats):
        """손익 요약 업데이트"""
        total_count = stats.get('total_count', 0)
        total_volume = stats.get('total_volume', 0)
        total_fee = stats.get('total_fee', 0)
        total_pnl = stats.get('total_pnl', 0)
        
        self.total_trades_label.setText(f"총 거래: {total_count}건")
        self.total_volume_label.setText(f"총 거래량: {total_volume:.2f} USDT")
        self.total_fee_label.setText(f"총 수수료: {total_fee:.6f} USDT")
        
        if total_pnl > 0:
            pnl_color = "color: #00ff00;"
            pnl_text = f"총 손익: +{total_pnl:.2f} USDT"
        elif total_pnl < 0:
            pnl_color = "color: #ff4444;"
            pnl_text = f"총 손익: {total_pnl:.2f} USDT"
        else:
            pnl_color = "color: white;"
            pnl_text = f"총 손익: {total_pnl:.2f} USDT"
            
        self.total_pnl_label.setText(pnl_text)
        self.total_pnl_label.setStyleSheet(pnl_color)

    def export_to_excel(self):
        """엑셀 내보내기"""
        try:
            import pandas as pd
        except ImportError:
            QMessageBox.warning(self, "오류", "엑셀 내보내기를 위해 pandas와 openpyxl 패키지가 필요합니다.\npip install pandas openpyxl 명령으로 설치해주세요.")
            return

        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "엑셀 파일 저장", 
                f"거래내역_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", 
                "Excel files (*.xlsx)"
            )
            
            if not file_path:
                return
            
            # 현재 표시된 모든 거래 데이터 (최대 200개)
            data = []
            for trade in self.all_trades:
                data.append({
                    '시간': trade.get('trade_time'),
                    '심볼': trade.get('symbol'),
                    '방향': trade.get('side'),
                    '타입': trade.get('trade_type'),
                    '수량': trade.get('quantity'),
                    '가격': trade.get('price'),
                    '레버리지': trade.get('leverage'),
                    '수수료': trade.get('commission'),
                    '실현손익': trade.get('realized_pnl')
                })
            
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False, engine='openpyxl')
            
            QMessageBox.information(self, "완료", f"엑셀 파일이 저장되었습니다:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"엑셀 내보내기 중 오류: {str(e)}")