from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QGroupBox, QCheckBox, QMessageBox)
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtGui import QFont
import asyncio
from binance_client import BinanceClient  # 직접 바이낸스 클라이언트 사용

class AccountWidget(QWidget):
    api_connected = pyqtSignal(str, str, bool)  # api_key, secret_key, testnet
    
    def __init__(self):
        super().__init__()
        self.client = None
        self.update_timer = None
        self.init_ui()
        
    def init_ui(self):
        self.setMaximumWidth(420)
        layout = QVBoxLayout(self)
        
        # API 연결 섹션
        api_group = QGroupBox("API 연결")
        api_layout = QVBoxLayout(api_group)
        
        # API Key 입력
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("API Key 입력")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(QLabel("API Key:"))
        api_layout.addWidget(self.api_key_input)
        
        # Secret Key 입력
        self.secret_key_input = QLineEdit()
        self.secret_key_input.setPlaceholderText("Secret Key 입력")
        self.secret_key_input.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(QLabel("Secret Key:"))
        api_layout.addWidget(self.secret_key_input)
        
        # 테스트넷 체크박스
        self.testnet_checkbox = QCheckBox("테스트넷 사용")
        self.testnet_checkbox.setChecked(True)
        api_layout.addWidget(self.testnet_checkbox)
        
        # 연결 버튼
        self.connect_btn = QPushButton("연결")
        self.connect_btn.clicked.connect(self.connect_api)
        api_layout.addWidget(self.connect_btn)
        
        # 연결 해제 버튼 (처음에는 숨김)
        self.disconnect_btn = QPushButton("연결 해제")
        self.disconnect_btn.clicked.connect(self.disconnect_api)
        self.disconnect_btn.setVisible(False)
        self.disconnect_btn.setStyleSheet("""
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
        api_layout.addWidget(self.disconnect_btn)
        
        layout.addWidget(api_group)
        
        # 계좌 정보 섹션
        account_group = QGroupBox("계좌 정보")
        account_layout = QVBoxLayout(account_group)
        
        # 잔고 정보
        self.total_balance_label = QLabel("총 자산: -")
        self.available_balance_label = QLabel("사용가능: -")
        self.position_margin_label = QLabel("포지션 마진: -")
        self.unrealized_pnl_label = QLabel("미실현 손익: -")
        
        # 폰트 설정
        font = QFont("맑은 고딕", 10, QFont.Bold)
        for label in [self.total_balance_label, self.available_balance_label, 
                     self.position_margin_label, self.unrealized_pnl_label]:
            label.setFont(font)
            account_layout.addWidget(label)
            
        layout.addWidget(account_group)
        
        # 🔥 새로고침 버튼 추가
        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton("🔄 새로고침")
        self.refresh_button.clicked.connect(self.manual_refresh)
        self.refresh_button.setEnabled(False)
        button_layout.addWidget(self.refresh_button)
        
        # 자동 업데이트 상태 표시
        self.auto_update_label = QLabel("⏱️ 자동 업데이트: 1분마다")
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
            QLineEdit {
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
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QLabel {
                color: white;
                padding: 2px;
            }
            QCheckBox {
                color: white;
            }
        """)
        
    def manual_refresh(self):
        """수동 새로고침"""
        if self.client:
            print("🔄 수동 새로고침 실행...")
            asyncio.create_task(self.update_account_info())


    def connect_api(self):
            """API 연결"""
            api_key = self.api_key_input.text().strip()
            secret_key = self.secret_key_input.text().strip()
            testnet = self.testnet_checkbox.isChecked()
            
            if not api_key or not secret_key:
                QMessageBox.warning(self, "경고", "API Key와 Secret Key를 입력해주세요.")
                return
                
            # 버튼 상태 변경 (연결 중)
            self.connect_btn.setText("연결 중...")
            self.connect_btn.setEnabled(False)
            
            # API 검증 후 연결
            self.validate_and_connect(api_key, secret_key, testnet)
        
    def validate_and_connect(self, api_key, secret_key, testnet):
        """API 키 검증 후 연결"""
        mode = "테스트넷" if testnet else "실전"
        print(f"\n{'='*50}")
        print(f"🔄 {mode} 모드로 API 연결 시도")
        print(f"{'='*50}")
        
        QTimer.singleShot(100, lambda: asyncio.create_task(self._validate_async(api_key, secret_key, testnet)))
        
    async def _validate_async(self, api_key, secret_key, testnet):
        """실제 검증 로직 - 직접 바이낸스 API"""
        try:
            mode = "테스트넷" if testnet else "실전"
            print(f"📡 {mode} API 검증 시작...")
            
            # 임시 클라이언트로 API 키 검증
            temp_client = BinanceClient(api_key, secret_key, testnet)
            account_info = await temp_client.get_account_info()
            
            # 🔥 검증 성공 여부 확인
            if account_info and 'totalWalletBalance' in account_info:
                print(f"✅ {mode} API 키 검증 성공!")
                
                # 🔥 메인 클라이언트로 저장
                self.client = temp_client
                
                # 🔥 UI 업데이트는 QTimer로 메인 스레드에서 실행
                QTimer.singleShot(0, lambda: self._update_ui_on_connect(api_key, secret_key, testnet))
                
                print(f"🚀 {mode} 모드 API 연결 완료!")
                
            else:
                raise Exception("API 키 검증 실패 - 계정 정보를 가져올 수 없습니다.")
                
        except Exception as e:
            print(f"❌ {mode} API 키 검증 실패: {e}")
            
            # 🔥 UI 업데이트는 QTimer로 메인 스레드에서 실행
            QTimer.singleShot(0, lambda: self._update_ui_on_error(e, mode))
            
            # 세션 정리
            if hasattr(temp_client, 'session') and temp_client.session:
                await temp_client.close()
    
    def _update_ui_on_connect(self, api_key, secret_key, testnet):
        """연결 성공 시 UI 업데이트 (메인 스레드에서 실행)"""
        # 연결 성공 신호 발송
        self.api_connected.emit(api_key, secret_key, testnet)
        
        # 🔥 버튼 상태 변경 - 기존 클릭 이벤트 연결 해제 후 재연결
        try:
            self.connect_btn.clicked.disconnect()
        except:
            pass  # 이미 연결 해제되어 있을 수 있음
        
        self.connect_btn.setText("연결 해제")
        self.connect_btn.setEnabled(True)
        self.connect_btn.clicked.connect(self.disconnect_api)
        
        # 입력 필드 비활성화
        self.api_key_input.setEnabled(False)
        self.secret_key_input.setEnabled(False)
        self.testnet_checkbox.setEnabled(False)
        
        # 🔥 계좌 정보 업데이트 시작
        self.start_updates(self.client)
    
    def _update_ui_on_error(self, error, mode):
        """연결 실패 시 UI 업데이트 (메인 스레드에서 실행)"""
        # 연결 실패 시 버튼 복원
        self.connect_btn.setText("연결")
        self.connect_btn.setEnabled(True)
        
        # 오류 메시지 표시
        QMessageBox.critical(
            self,
            "API 연결 실패",
            f"{mode} 바이낸스 API 연결에 실패했습니다.\n\n"
            f"오류: {error}\n\n"
            f"API 키와 Secret 키를 확인해주세요."
        )
        
    def disconnect_api(self):
        """API 연결 해제"""
        self.reset_connection_state()
        
        # 계좌 정보 초기화
        self.total_balance_label.setText("총 자산: -")
        self.available_balance_label.setText("사용가능: -")
        self.position_margin_label.setText("포지션 마진: -")
        self.unrealized_pnl_label.setText("미실현 손익: -")
        
        # 타이머 중지
        if self.update_timer:
            self.update_timer.stop()
            
        QMessageBox.information(self, "알림", "API 연결이 해제되었습니다.")
        
    def reset_connection_state(self):
        """연결 상태 초기화"""
        # 🔥 버튼 클릭 이벤트 재연결
        try:
            self.connect_btn.clicked.disconnect()
        except:
            pass
        
        self.connect_btn.setText("연결")
        self.connect_btn.setEnabled(True)
        self.connect_btn.clicked.connect(self.connect_api)
        
        # 입력 필드 활성화
        self.api_key_input.setEnabled(True)
        self.secret_key_input.setEnabled(True)
        self.testnet_checkbox.setEnabled(True)

    def start_updates(self, client):
        """계좌 정보 업데이트 시작"""
        self.client = client
        
        # 🔥 새로고침 버튼 활성화
        self.refresh_button.setEnabled(True)
        
        # 즉시 한 번 업데이트
        asyncio.create_task(self.update_account_info())
        
        # 🔥 타이머로 주기적 업데이트 (1분마다 = 60,000ms)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(lambda: asyncio.create_task(self.update_account_info()))
        self.update_timer.start(60000)  # 1분 = 60초 = 60,000ms
        
        print("✅ 계정정보 자동 업데이트: 1분마다")
        
    async def update_account_info(self):
        """계좌 정보 업데이트 - 직접 바이낸스 API 사용"""
        if not self.client:
            print("클라이언트가 없습니다.")
            return
            
        try:
            # print("=== 직접 바이낸스 계좌 정보 업데이트 ===")
            
            # 직접 바이낸스 API에서 계좌 정보 가져오기
            account_info = await self.client.get_account_info()
            # print(f"계좌 정보: {account_info}")
            
            if not account_info:
                print("계좌 정보가 None입니다.")
                return
                
            # 바이낸스 API 원본 필드 사용
            total_balance = float(account_info.get('totalWalletBalance', 0))
            available_balance = float(account_info.get('availableBalance', 0))
            position_margin = float(account_info.get('totalPositionInitialMargin', 0))
            unrealized_pnl = float(account_info.get('totalUnrealizedProfit', 0))
            
            # print(f"파싱된 계좌 정보 - total: {total_balance}, available: {available_balance}, margin: {position_margin}, pnl: {unrealized_pnl}")
            
            # UI 업데이트
            # print("UI 업데이트 시작...")
            self.total_balance_label.setText(f"총 자산: {total_balance:.2f} USDT")
            self.available_balance_label.setText(f"사용가능: {available_balance:.2f} USDT")
            self.position_margin_label.setText(f"포지션 마진: {position_margin:.2f} USDT")
            
            # 미실현 손익률 계산
            if position_margin > 0:
                pnl_rate = (unrealized_pnl / position_margin) * 100
                if unrealized_pnl > 0:
                    pnl_color = "color: #00ff00;"
                    pnl_text = f"미실현 손익: +{unrealized_pnl:.2f} USDT (+{pnl_rate:.2f}%)"
                elif unrealized_pnl < 0:
                    pnl_color = "color: #ff4444;"
                    pnl_text = f"미실현 손익: {unrealized_pnl:.2f} USDT ({pnl_rate:.2f}%)"
                else:
                    pnl_color = "color: white;"
                    pnl_text = f"미실현 손익: {unrealized_pnl:.2f} USDT (0.00%)"
            else:
                pnl_color = "color: white;"
                pnl_text = f"미실현 손익: {unrealized_pnl:.2f} USDT"
                
            self.unrealized_pnl_label.setText(pnl_text)
            self.unrealized_pnl_label.setStyleSheet(pnl_color)
            
            print(f"UI 업데이트 완료: 총자산={total_balance}, 사용가능={available_balance}, 마진={position_margin}, 손익={unrealized_pnl}")
                
        except Exception as e:
            print(f"계좌 정보 업데이트 오류: {e}")
            import traceback
            traceback.print_exc()
            
    def closeEvent(self, event):
        """위젯 종료 시 타이머 정리"""
        if self.update_timer:
            self.update_timer.stop()
        event.accept()