import sys
import os
import asyncio
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QTabWidget, QScrollArea, QMessageBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import qasync

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from binance_client import BinanceClient
from widgets.account_widget import AccountWidget
from widgets.trading_widget import TradingWidget
from widgets.position_widget import PositionWidget
from widgets.trade_history_widget import TradeHistoryWidget
from widgets.orderbook_widget import OrderbookWidget
from widgets.order_queue_widget import OrderQueueWidget
from widgets.strategy_widget import StrategyWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.binance_client = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("바이낸스 선물 거래 시스템 v2.0 - AI 시그널 통합")
        self.setGeometry(100, 100, 1600, 900)  # 🔥 전체 창 크기 증가
        self.setMinimumSize(1400, 700)  # 🔥 최소 크기 증가

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # 1. 모든 위젯 객체를 먼저 생성합니다.
        self.account_widget = AccountWidget()
        self.trading_widget = TradingWidget()
        self.strategy_widget = StrategyWidget()
        self.position_widget = PositionWidget()
        self.trade_history_widget = TradeHistoryWidget()
        self.orderbook_widget = OrderbookWidget()
        self.order_queue_widget = OrderQueueWidget()

        # 2. 생성된 위젯들의 시그널-슬롯을 연결합니다.
        self.account_widget.api_connected.connect(self.on_api_connected)
        self.account_widget.disconnect_btn.clicked.connect(self.on_api_disconnected)
        self.strategy_widget.db_connected.connect(self.on_db_connected)
        self.strategy_widget.trade_executed.connect(self.position_widget.update_positions)
        self.strategy_widget.trade_executed.connect(self.order_queue_widget.update_orders)
        self.strategy_widget.trade_executed.connect(self.trade_history_widget.load_trade_history)

        # 3. 🔥 왼쪽 패널 (크기 고정)
        left_panel = QVBoxLayout()
        left_panel.addWidget(self.account_widget)
        left_panel.addWidget(self.strategy_widget)
        left_panel.addWidget(self.trading_widget)
        

        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        
        # 🔥 왼쪽 스크롤 영역 크기 제한
        left_scroll = QScrollArea()
        left_scroll.setWidget(left_widget)
        left_scroll.setWidgetResizable(True)
        left_scroll.setMaximumWidth(480)  # 🔥 최대 너비 제한 (500 → 480)
        left_scroll.setMinimumWidth(450)  # 🔥 최소 너비 유지

        # 🔥 오른쪽 패널
        right_panel = QVBoxLayout()
        tab_widget = QTabWidget()
        tab_widget.addTab(self.position_widget, "포지션")
        tab_widget.addTab(self.trade_history_widget, "거래내역")
        tab_widget.addTab(self.orderbook_widget, "호가")
        tab_widget.addTab(self.order_queue_widget, "주문대기열")
        right_panel.addWidget(tab_widget)
        right_widget = QWidget()
        right_widget.setLayout(right_panel)

        # 🔥 메인 레이아웃에 추가 (비율 조정)
        main_layout.addWidget(left_scroll)
        main_layout.addWidget(right_widget)
        
        # 🔥 왼쪽:오른쪽 비율 = 1:3 (기존 1:2에서 변경)
        main_layout.setStretch(0, 1)  # 왼쪽 패널
        main_layout.setStretch(1, 3)  # 오른쪽 패널 (더 넓게)

        self.apply_styles()

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; color: white; }
            QScrollArea { background-color: #2b2b2b; border: none; }
            QScrollArea > QWidget > QWidget { background-color: #2b2b2b; }
            QScrollBar:vertical { background-color: #404040; width: 12px; border-radius: 6px; border: none; }
            QScrollBar::handle:vertical { background-color: #606060; border-radius: 6px; min-height: 20px; border: none; }
            QScrollBar::handle:vertical:hover { background-color: #707070; }
            QMessageBox { background-color: #3c3c3c; color: white; }
            QMessageBox QLabel { color: white; background-color: transparent; }
            QMessageBox QPushButton { background-color: #0078d4; color: white; border: none; padding: 6px 12px; border-radius: 3px; min-width: 60px; }
            QMessageBox QPushButton:hover { background-color: #106ebe; }
            QTabWidget::pane { border: 1px solid #555; background-color: #3c3c3c; }
            QTabBar::tab { background-color: #555; color: white; padding: 8px 16px; margin-right: 2px; border: none; }
            QTabBar::tab:selected { background-color: #0078d4; }
        """)

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self, "프로그램 종료",
            "프로그램을 종료하시겠습니까?\n\n• 미체결 주문과 포지션은 그대로 유지됩니다.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.on_api_disconnected()
            print("✅ 프로그램이 안전하게 종료됩니다.")
            event.accept()
        else:
            event.ignore()

    def on_db_connected(self, db_config):
        """DB 연결 성공 시 다른 위젯에 DB 설정을 전달합니다."""
        print("메인 윈도우: DB 연결 감지. 거래내역 위젯에 설정 전달...")
        
        # 🔥 PositionWidget에 db_manager 전달
        if hasattr(self.strategy_widget, 'db_manager') and self.strategy_widget.db_manager:
            self.position_widget.set_db_manager(self.strategy_widget.db_manager)
        
        # 🔥 TradingWidget에 db_config 전달 (set_db_config 사용)
        self.trading_widget.set_db_config(db_config)
        
        # 🔥 TradeHistoryWidget에 db_config 전달
        self.trade_history_widget.set_db_config(db_config)

    def on_api_connected(self, api_key, secret_key, testnet=True):
        """API 연결 성공 시 모든 위젯에 클라이언트 전달"""
        mode = "테스트넷" if testnet else "실전"
        print(f"\n{'='*60}")
        print(f"🔄 메인 윈도우: {mode} API 연결 처리 중...")
        print(f"{'='*60}")
        
        try:
            # 🔥 수정: account_widget에서 이미 생성한 클라이언트 재사용
            if hasattr(self.account_widget, 'client') and self.account_widget.client:
                self.binance_client = self.account_widget.client
                print(f"✅ {mode} 클라이언트 재사용 (account_widget에서)")
            else:
                # account_widget에 없으면 새로 생성
                self.binance_client = BinanceClient(api_key, secret_key, testnet)
                print(f"✅ {mode} 바이낸스 클라이언트 새로 생성")
            
            # 모든 위젯에 클라이언트 객체 전달
            self.trading_widget.set_client(self.binance_client)
            self.position_widget.set_client(self.binance_client)
            self.orderbook_widget.set_client(self.binance_client)
            self.strategy_widget.set_client(self.binance_client)
            self.order_queue_widget.set_client(self.binance_client)
            
            print(f"✅ 모든 위젯에 {mode} 클라이언트 설정 완료")
            
            # 계좌 정보 업데이트 시작 (이미 account_widget에서 시작했을 수 있음)
            if not self.account_widget.update_timer or not self.account_widget.update_timer.isActive():
                self.account_widget.start_updates(self.binance_client)
            
            print(f"🚀 {mode} 모드 준비 완료!")

        except Exception as e:
            print(f"❌ {mode} 바이낸스 API 연결 실패: {e}")
            import traceback
            traceback.print_exc()

    def on_api_disconnected(self):
        """API 연결 해제 시 모든 관련 객체 정리 (안전 버전)"""
        print("API 연결 해제가 감지되었습니다. 관련 서비스를 중지합니다.")
        
        try:
            # 1. 자동매매 먼저 중지
            if self.strategy_widget:
                try:
                    self.strategy_widget.stop_auto_trading()
                except Exception as e:
                    print(f"⚠️ 자동매매 중지 중 오류 (무시): {e}")
            
            # 2. 클라이언트 세션 정리
            if self.binance_client:
                try:
                    # asyncio 태스크 생성하여 비동기 정리
                    import asyncio
                    asyncio.create_task(self.binance_client.close())
                except Exception as e:
                    print(f"⚠️ 클라이언트 종료 중 오류 (무시): {e}")
            
            self.binance_client = None
            
            # 3. 각 위젯 안전하게 정리
            widgets_with_client = [
                self.account_widget, self.trading_widget, self.position_widget,
                self.trade_history_widget, self.orderbook_widget,
                self.strategy_widget, self.order_queue_widget
            ]
            
            for widget in widgets_with_client:
                if not widget:
                    continue
                    
                try:
                    # 클라이언트 제거
                    widget.client = None
                    
                    # update_timer 안전하게 중지
                    if hasattr(widget, 'update_timer'):
                        timer = getattr(widget, 'update_timer', None)
                        if timer and hasattr(timer, 'stop'):
                            try:
                                if timer.isActive():
                                    timer.stop()
                            except RuntimeError:
                                pass  # 이미 삭제된 경우 무시
                    
                    # ticker_timer 안전하게 중지
                    if hasattr(widget, 'ticker_timer'):
                        timer = getattr(widget, 'ticker_timer', None)
                        if timer and hasattr(timer, 'stop'):
                            try:
                                if timer.isActive():
                                    timer.stop()
                            except RuntimeError:
                                pass
                    
                    # price_timer 안전하게 중지
                    if hasattr(widget, 'price_timer'):
                        timer = getattr(widget, 'price_timer', None)
                        if timer and hasattr(timer, 'stop'):
                            try:
                                if timer.isActive():
                                    timer.stop()
                            except RuntimeError:
                                pass
                                
                except Exception as e:
                    print(f"⚠️ 위젯 정리 중 오류 (무시): {e}")
            
            print("✅ API 연결 해제 완료")
            
        except Exception as e:
            print(f"❌ 연결 해제 중 오류: {e}")
            import traceback
            traceback.print_exc()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AI Trading System")
    app.setFont(QFont("맑은 고딕", 9))
    app.setStyleSheet("QApplication { background-color: #1e1e1e; color: white; }")
    
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = MainWindow()
    window.show()

    print("🚀 바이낸스 선물 거래 시스템 시작!")

    try:
        with loop:
            loop.run_forever()
    except KeyboardInterrupt:
        print("\n👋 사용자에 의해 프로그램이 종료되었습니다.")
    finally:
        print("📚 프로그램 종료")

if __name__ == '__main__':
    main()