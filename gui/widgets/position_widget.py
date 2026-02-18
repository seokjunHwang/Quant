# position_widget.py - 완전 수정본 (바이낸스 API 직접 조회)

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QMessageBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
import asyncio

class PositionWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.client = None
        self.update_timer = None
        self.db_manager = None  
        self._update_lock = asyncio.Lock()  
        self.init_ui()
        self._update_task = None
        self.precision_cache = {}

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 미결제약정 요약 섹션
        summary_group = QGroupBox("미결제약정 요약")
        summary_layout = QVBoxLayout(summary_group)

        summary_info_layout = QHBoxLayout()

        self.total_positions_label = QLabel("총 포지션: 0개")
        self.total_margin_label = QLabel("총 마진: 0 USDT")
        self.total_pnl_label = QLabel("총 손익: 0 USDT")

        font = QFont("맑은 고딕", 10, QFont.Bold)
        for label in [self.total_positions_label, self.total_margin_label, self.total_pnl_label]:
            label.setFont(font)
            summary_info_layout.addWidget(label)

        summary_layout.addLayout(summary_info_layout)
        
        # 🔥 수동 조회 버튼 레이아웃 (API 최적화)
        button_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("🔄 포지션 조회")
        self.refresh_button.clicked.connect(self.manual_refresh)
        button_layout.addWidget(self.refresh_button)
        
        # 자동 업데이트 상태 표시
        self.auto_update_label = QLabel("⏱️ 자동 업데이트: 1분마다 (거래 시 즉시)")
        self.auto_update_label.setStyleSheet("color: #888; font-size: 10px;")
        button_layout.addWidget(self.auto_update_label)
        button_layout.addStretch()
        
        summary_layout.addLayout(button_layout)
        layout.addWidget(summary_group)

        # 포지션 테이블 섹션
        table_group = QGroupBox("보유 포지션")
        table_layout = QVBoxLayout(table_group)

        self.position_table = QTableWidget()
        self.position_table.setColumnCount(10)
        self.position_table.setHorizontalHeaderLabels([
            "심볼", "방향", "레버리지", "수량", "진입가", 
            "현재가", "미실현손익", "수익률(%)", "마진", "청산"
        ])
        self.position_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        self.position_table.setStyleSheet("""
            QTableWidget { 
                background-color: #2b2b2b; color: white; gridline-color: #555; 
                border: 1px solid #555; alternate-background-color: #353535; 
            }
            QHeaderView::section { 
                background-color: #444; color: white; padding: 8px; 
                border: 1px solid #555; font-weight: bold; 
            }
        """)

        table_layout.addWidget(self.position_table)
        layout.addWidget(table_group)

        # 🔥 기존 새로고침 버튼 (하단) - 제거하거나 유지 가능
        # self.refresh_button = QPushButton("새로고침")
        # self.refresh_button.clicked.connect(self.update_positions)
        # layout.addWidget(self.refresh_button)

        self.setStyleSheet("""
            QGroupBox { 
                font-weight: bold; border: 1px solid #666; border-radius: 5px; 
                margin-top: 10px; background-color: #3c3c3c; color: white; 
            }
            QGroupBox::title { 
                subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px; 
            }
            QPushButton { 
                background-color: #0078d4; border: none; border-radius: 3px; 
                padding: 8px; color: white; font-weight: bold; 
            }
            QPushButton:hover { 
                background-color: #106ebe; 
            }
            QLabel { 
                color: white; padding: 2px; 
            }
        """)

    def manual_refresh(self):
        """수동 포지션 조회"""
        if self.client:
            print("🔄 수동 포지션 조회 실행...")
            asyncio.create_task(self._update_positions_async())

    async def get_quantity_precision(self, symbol):
        """
        바이낸스 API에서 심볼의 수량 정밀도를 조회 (캐싱)
        
        Returns:
            int: 소수점 자릿수 (예: 3 = 0.001, 0 = 정수만)
        """
        # 캐시에 있으면 바로 반환
        if symbol in self.precision_cache:
            return self.precision_cache[symbol]
        
        try:
            print(f"   📡 {symbol} 정밀도 API 조회 중...")
            symbol_info = await self.client.get_symbol_info(symbol)
            
            if symbol_info:
                quantity_precision = symbol_info.get('quantityPrecision', 3)
                self.precision_cache[symbol] = quantity_precision
                print(f"   ✅ {symbol} 수량 정밀도: {quantity_precision}자리")
                return quantity_precision
            else:
                print(f"   ⚠️ {symbol} 정보 없음 - 기본값 3 사용")
                return 3
                
        except Exception as e:
            print(f"   ⚠️ {symbol} 정밀도 조회 실패: {e}")
            return 3  # 기본값

    def set_client(self, client):
        self.client = client
        if self.client:
            asyncio.create_task(self._update_positions_async())
        
        # 🔥 1분마다 자동 업데이트
        if not self.update_timer:
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self.update_positions)
            self.update_timer.start(60000)  # 1분 = 60,000ms
            print("✅ 포지션 자동 업데이트: 1분마다")

    def set_db_manager(self, db_manager):
        """DB 매니저 설정"""
        self.db_manager = db_manager
        print("✅ PositionWidget에 DB 매니저 연결됨")

    def update_positions(self):
        """포지션 업데이트 (비동기 태스크 생성)"""
        if self.client:
            asyncio.create_task(self._update_positions_async())
    # 거래 실행 시 즉시 업데이트
    async def _update_positions_async(self):
        """실제 포지션 업데이트"""
        if self._update_task and not self._update_task.done():
            print("⏳ 이전 업데이트가 진행 중입니다. 대기...")
            await self._update_task
            return
        
        self._update_task = asyncio.current_task()
        
        try:
            positions = await self.client.get_positions()
            if positions:
                await self.populate_position_table(positions)
            else:
                self.position_table.setRowCount(0)
                self.update_summary([], 0, 0)
        except Exception as e:
            print(f"포지션 업데이트 오류: {e}")
        finally:
            self._update_task = None

    async def populate_position_table(self, positions):
        try:
            self.position_table.setRowCount(len(positions))
            total_pnl = 0
            total_margin = 0

            for row, position in enumerate(positions):
                symbol = position.get('symbol', '')
                position_amt = float(position.get('positionAmt', 0))
                entry_price = float(position.get('entryPrice', 0))
                mark_price = float(position.get('markPrice', 0))
                unrealized_pnl = float(position.get('unRealizedProfit', 0))
                leverage = float(position.get('leverage', 1))

                notional_value = abs(position_amt) * entry_price
                position_margin = notional_value / leverage if leverage > 0 else 0

                commission = notional_value * 0.0004
                pnl_after_fee = unrealized_pnl - commission

                if position_margin > 0:
                    roe_percent = (pnl_after_fee / position_margin) * 100
                else:
                    roe_percent = 0

                side = "LONG" if position_amt > 0 else "SHORT"
                side_color = QColor(0, 255, 0) if position_amt > 0 else QColor(255, 68, 68)

                # ✅ 수정: 헤더 순서에 맞게 items 배열 재정렬
                # 헤더: ["심볼", "방향", "레버리지", "수량", "진입가", "현재가", "미실현손익", "수익률(%)", "마진", "청산"]
                items = [
                    QTableWidgetItem(symbol),                        # 0: 심볼
                    QTableWidgetItem(side),                          # 1: 방향
                    QTableWidgetItem(f"{int(leverage)}x"),           # 2: 레버리지 ✅
                    QTableWidgetItem(f"{abs(position_amt):.4f}"),    # 3: 수량 ✅
                    QTableWidgetItem(f"{entry_price:.4f}"),          # 4: 진입가 ✅
                    QTableWidgetItem(f"{mark_price:.4f}"),           # 5: 현재가
                    QTableWidgetItem(f"{pnl_after_fee:+.2f}"),       # 6: 미실현손익
                    QTableWidgetItem(f"{roe_percent:.2f}%"),         # 7: 수익률(%)
                    QTableWidgetItem(f"{position_margin:.2f}"),      # 8: 마진
                ]

                for col, item in enumerate(items):
                    item.setTextAlignment(Qt.AlignCenter)
                    if col == 1:  # 방향
                        item.setForeground(side_color)
                    elif col == 6:  # 미실현손익
                        item.setForeground(QColor(0, 255, 0) if pnl_after_fee > 0 else QColor(255, 68, 68))
                    elif col == 7:  # 수익률
                        item.setForeground(QColor(0, 255, 0) if roe_percent > 0 else QColor(255, 68, 68))
                    self.position_table.setItem(row, col, item)

                # 청산 버튼 (9번 컬럼)
                close_button = QPushButton("청산")
                close_button.setStyleSheet("""
                    QPushButton { 
                        background-color: #cc0000; 
                        color: white; 
                        font-weight: bold; 
                        padding: 5px; 
                        border: none; 
                        border-radius: 3px; 
                    }
                    QPushButton:hover { 
                        background-color: #aa0000; 
                    }
                """)
                close_button.clicked.connect(lambda ch, s=symbol: asyncio.create_task(self.close_position(s)))
                self.position_table.setCellWidget(row, 9, close_button)

                total_pnl += pnl_after_fee
                total_margin += position_margin

            self.update_summary(positions, total_margin, total_pnl)
        except Exception as e:
            print(f"테이블 업데이트 오류: {e}")

    def update_summary(self, positions, total_margin, total_pnl):
        self.total_positions_label.setText(f"이 포지션: {len(positions)}개")
        self.total_margin_label.setText(f"이 마진: {total_margin:.2f} USDT")
        pnl_text = f"이 손익: {total_pnl:+.2f} USDT"
        self.total_pnl_label.setText(pnl_text)
        if total_pnl != 0:
            pnl_color = "color: #00ff00;" if total_pnl > 0 else "color: #ff4444;"
            self.total_pnl_label.setStyleSheet(pnl_color)
        else:
            self.total_pnl_label.setStyleSheet("color: white;")

    async def close_position(self, symbol):
        """단일 포지션 청산 (🔥 바이낸스 API로 정밀도 조회)"""
        try:
            print(f"\n{'='*70}")
            print(f"🔥 {symbol} 포지션 청산 시작")
            print(f"{'='*70}")
            
            # 1️⃣ 현재 포지션 조회
            positions = await self.client.get_positions()
            
            if not positions:
                print(f"❌ 포지션 정보를 가져올 수 없습니다.")
                QMessageBox.warning(self, "오류", "포지션 정보를 가져올 수 없습니다.")
                return False
            
            print(f"이 활성 포지션 수: {len([p for p in positions if float(p.get('positionAmt', 0)) != 0])}")
            
            # 2️⃣ 해당 심볼의 포지션 찾기
            target_position = None
            for pos in positions:
                if pos.get('symbol') == symbol:
                    position_amt = float(pos.get('positionAmt', 0))
                    if position_amt != 0:
                        target_position = pos
                        break
            
            if not target_position:
                print(f"❌ {symbol} 포지션이 존재하지 않습니다.")
                QMessageBox.warning(self, "오류", f"{symbol} 포지션이 존재하지 않습니다.")
                return False
            
            # 3️⃣ 청산 정보 추출
            position_amt = float(target_position['positionAmt'])
            position_side = 'LONG' if position_amt > 0 else 'SHORT'
            side = 'SELL' if position_amt > 0 else 'BUY'
            quantity = abs(position_amt)
            entry_price = float(target_position.get('entryPrice', 0))
            mark_price = float(target_position.get('markPrice', 0))
            leverage = int(float(target_position.get('leverage', 1)))
            unrealized_pnl = float(target_position.get('unRealizedProfit', 0))
            
            print(f"📋 청산 주문: {side} {quantity}")
            print(f"   - 포지션 방향: {position_side}")
            print(f"   - 진입가: {entry_price}")
            print(f"   - 현재가: {mark_price}")
            print(f"   - 미실현 손익: {unrealized_pnl:.2f} USDT")
            
            # 4️⃣ 🔥 바이낸스 API에서 정밀도 조회 후 수량 조정
            precision = await self.get_quantity_precision(symbol)
            adjusted_qty = round(quantity, precision)
            
            # 최소값 보장
            min_val = 1 if precision == 0 else 10 ** (-precision)
            if adjusted_qty < min_val:
                adjusted_qty = min_val
                print(f"   ⚠️ 최소 수량으로 조정: {adjusted_qty}")
            
            print(f"   - 원본 수량: {quantity}")
            print(f"   - 정밀도: {precision}자리")
            print(f"   - 조정된 수량: {adjusted_qty}")
            
            # 5️⃣ 청산 주문 실행
            result = await self.client.place_order(
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=adjusted_qty
            )
            
            # 6️⃣ 결과 확인
            if result and 'orderId' in result:
                print(f"✅ {symbol} 청산 성공!")
                print(f"   주문 ID: {result['orderId']}")
                
                # 실제 체결 정보 조회
                await asyncio.sleep(1)
                
                # 수수료 계산
                notional = quantity * mark_price
                commission = notional * 0.0004
                pnl = unrealized_pnl - commission
                
                print(f"   - 실현 손익: {pnl:.2f} USDT")
                print(f"   - 수수료: {commission:.4f} USDT")
                
                # DB 저장
                if self.db_manager:
                    from datetime import datetime
                    save_result = self.db_manager.save_trade({
                        'order_id': result['orderId'],
                        'symbol': symbol,
                        'side': position_side,
                        'trade_type': 'EXIT',
                        'quantity': adjusted_qty,
                        'price': mark_price,
                        'leverage': leverage,
                        'realized_pnl': pnl,
                        'commission': commission,
                        'trade_time': datetime.now()
                    })
                    
                    if save_result:
                        print(f"   ✅ 거래내역 DB 저장 완료")
                    else:
                        print(f"   ⚠️ DB 저장 실패 (하지만 청산은 성공)")
                else:
                    print(f"   ⚠️ DB 매니저가 없어 거래내역 저장 안됨")
                
                # 포지션 업데이트
                await self._update_positions_async()
                
                QMessageBox.information(self, "청산 완료", f"{symbol} 포지션이 청산되었습니다.\n손익: {pnl:.2f} USDT")
                return True
                
            else:
                # 에러 처리
                error_msg = result.get('msg', '알 수 없는 오류') if result else 'API 응답 없음'
                print(f"❌ 청산 실패: {error_msg}")
                
                # 실제 포지션 상태 재확인
                await asyncio.sleep(2)
                positions_after = await self.client.get_positions()
                
                position_still_exists = False
                for pos in positions_after:
                    if pos.get('symbol') == symbol:
                        position_amt_after = float(pos.get('positionAmt', 0))
                        if position_amt_after != 0:
                            position_still_exists = True
                            break
                
                if not position_still_exists:
                    print(f"⚠️ API 에러 있었지만 포지션은 실제로 청산됨!")
                    await self._update_positions_async()
                    return True
                
                QMessageBox.critical(self, "청산 실패", f"{symbol} 청산에 실패했습니다.\n오류: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ 청산 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "오류", f"청산 중 오류가 발생했습니다:\n{str(e)}")
            return False

    def close_all_positions(self):
        """모든 포지션 청산"""
        asyncio.create_task(self._close_all_positions_async())




    async def _close_all_positions_async(self):
        """모든 포지션 청산 실행 (DB 저장 포함)"""
        try:
            print("\n🚨 모든 포지션 청산 시작")
            
            current_positions = await self.client.get_positions()
            
            active_positions = []
            for pos in current_positions:
                position_amt = float(pos.get('positionAmt', 0))
                if position_amt != 0:
                    active_positions.append(pos)
            
            if not active_positions:
                print("❌ 청산할 포지션이 없습니다.")
                QMessageBox.information(self, "알림", "청산할 포지션이 없습니다.")
                return
            
            print(f"📊 청산할 포지션: {len(active_positions)}개")
            
            # 청산 실행 (메시지 없이)
            success_count = 0
            failed_symbols = []
            
            for pos in active_positions:
                symbol = pos.get('symbol')
                
                try:
                    position_amt = float(pos.get('positionAmt', 0))
                    position_side = 'LONG' if position_amt > 0 else 'SHORT'
                    close_side = 'SELL' if position_amt > 0 else 'BUY'
                    close_qty = abs(position_amt)
                    
                    entry_price = float(pos.get('entryPrice', 0))
                    mark_price = float(pos.get('markPrice', 0))
                    leverage = int(float(pos.get('leverage', 1)))
                    unrealized_pnl = float(pos.get('unRealizedProfit', 0))
                    
                    # 정밀도 조회
                    precision = await self.get_quantity_precision(symbol)
                    adjusted_qty = round(close_qty, precision)
                    min_val = 1 if precision == 0 else 10 ** (-precision)
                    if adjusted_qty < min_val:
                        adjusted_qty = min_val
                    
                    print(f"   청산 중: {symbol} {position_side} {adjusted_qty}")
                    
                    # 청산 주문
                    result = await self.client.place_order(
                        symbol=symbol,
                        side=close_side,
                        order_type='MARKET',
                        quantity=adjusted_qty
                    )
                    
                    if result and 'orderId' in result:
                        success_count += 1
                        print(f"   ✅ {symbol} 청산 성공")
                        
                        # 🔥 DB 저장 추가
                        if self.db_manager:
                            # 수수료 계산
                            notional = close_qty * mark_price
                            commission = notional * 0.0004
                            pnl = unrealized_pnl - commission
                            
                            from datetime import datetime
                            self.db_manager.save_trade({
                                'order_id': result['orderId'],
                                'symbol': symbol,
                                'side': position_side,
                                'trade_type': 'EXIT',
                                'quantity': adjusted_qty,
                                'price': mark_price,
                                'leverage': leverage,
                                'realized_pnl': pnl,
                                'commission': commission,
                                'trade_time': datetime.now()
                            })
                            print(f"   ✅ {symbol} 거래내역 DB 저장 완료")
                        else:
                            print(f"   ⚠️ {symbol} DB 매니저 없음 (저장 스킵)")
                    else:
                        failed_symbols.append(symbol)
                        print(f"   ❌ {symbol} 청산 실패")
                    
                except Exception as e:
                    failed_symbols.append(symbol)
                    print(f"   ❌ {symbol} 청산 오류: {e}")
                
                await asyncio.sleep(0.5)
            
            print(f"\n✅ 모든 포지션 청산 완료: {success_count}/{len(active_positions)}")
            
            # 포지션 업데이트
            await self._update_positions_async()
            
            # 최종 결과 메시지
            if success_count == len(active_positions):
                QMessageBox.information(
                    self, 
                    "청산 완료", 
                    f"✅ 모든 포지션 청산 완료\n\n성공: {success_count}개"
                )
            else:
                fail_msg = f"실패한 종목:\n" + "\n".join(failed_symbols) if failed_symbols else ""
                QMessageBox.warning(
                    self, 
                    "청산 완료", 
                    f"⚠️ 일부 청산 실패\n\n"
                    f"성공: {success_count}개\n"
                    f"실패: {len(failed_symbols)}개\n\n"
                    f"{fail_msg}"
                )
            
        except Exception as e:
            print(f"❌ 전체 청산 오류: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "오류", f"청산 중 오류가 발생했습니다:\n{str(e)}")


    # ==================== 추가로 position_widget.py의 set_db_manager도 확인 ====================
    # position_widget.py 클래스에 이 메서드가 있는지 확인하세요