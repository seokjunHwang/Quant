# trading_gui.py
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QTextEdit

class TradingApp(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("코인 자동매매 GUI (테스트용)")
        self.setGeometry(200, 200, 400, 300)

        layout = QVBoxLayout()

        # 심볼 입력
        self.symbol_input = QLineEdit(self)
        self.symbol_input.setPlaceholderText("예: BTCUSDT")
        layout.addWidget(QLabel("코인 심볼"))
        layout.addWidget(self.symbol_input)

        # 버튼
        self.buy_button = QPushButton("매수")
        self.sell_button = QPushButton("매도")
        self.exit_button = QPushButton("포지션 종료")

        self.buy_button.clicked.connect(self.buy_action)
        self.sell_button.clicked.connect(self.sell_action)
        self.exit_button.clicked.connect(self.exit_action)

        layout.addWidget(self.buy_button)
        layout.addWidget(self.sell_button)
        layout.addWidget(self.exit_button)

        # 로그창
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(QLabel("시그널 로그"))
        layout.addWidget(self.log)

        self.setLayout(layout)

    def log_message(self, message):
        self.log.append(message)

    def buy_action(self):
        symbol = self.symbol_input.text()
        self.log_message(f"[매수] {symbol} 매수 주문 실행!")

    def sell_action(self):
        symbol = self.symbol_input.text()
        self.log_message(f"[매도] {symbol} 매도 주문 실행!")

    def exit_action(self):
        symbol = self.symbol_input.text()
        self.log_message(f"[종료] {symbol} 포지션 종료!")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TradingApp()
    window.show()
    sys.exit(app.exec_())
