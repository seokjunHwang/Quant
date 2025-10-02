import ccxt.async_support as ccxt
import asyncio
from decimal import Decimal, ROUND_DOWN

class CCXTBinanceClient:
    def __init__(self, api_key, secret_key, testnet=True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.testnet = testnet
        
        print(f"CCXT 클라이언트 초기화: testnet={testnet}")
        
        # CCXT 거래소 객체 생성
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret_key,
            'sandbox': testnet,  # 테스트넷 사용
            'options': {
                'defaultType': 'future',  # 선물 거래
            },
            'enableRateLimit': True,
        })
        
        print(f"CCXT 거래소 설정 완료: {self.exchange.id}")
        
    async def get_account_info(self):
        """계좌 정보 조회"""
        try:
            balance = await self.exchange.fetch_balance()
            
            # CCXT 형태를 바이낸스 API 형태로 변환
            account_info = {
                'totalWalletBalance': balance.get('USDT', {}).get('total', 0),
                'availableBalance': balance.get('USDT', {}).get('free', 0),
                'totalPositionInitialMargin': balance.get('used', 0),
                'totalUnrealizedProfit': 0  # 별도 계산 필요
            }
            
            # 미실현 손익 계산
            positions = await self.get_positions()
            total_unrealized_pnl = sum(
                float(pos.get('unrealizedPnl', 0)) 
                for pos in positions 
                if float(pos.get('contracts', 0)) != 0
            )
            account_info['totalUnrealizedProfit'] = total_unrealized_pnl
            
            return account_info
            
        except Exception as e:
            print(f"CCXT 계좌 정보 조회 오류: {e}")
            return None
    
    async def get_balance(self):
        """잔고 조회"""
        try:
            return await self.exchange.fetch_balance()
        except Exception as e:
            print(f"CCXT 잔고 조회 오류: {e}")
            return None
    
    async def get_positions(self):
        """포지션 정보 조회 - 레버리지 정보 개선"""
        try:
            positions = await self.exchange.fetch_positions()
            
            # CCXT 형태를 바이낸스 API 형태로 변환
            formatted_positions = []
            for pos in positions:
                if pos['contracts'] != 0:  # 활성 포지션만
                    # CCXT의 side 필드 확인
                    side = pos.get('side', '').upper()
                    contracts = pos['contracts']
                    
                    # 방향과 수량 정확히 처리
                    if side == 'SHORT':
                        position_amt = -abs(contracts)  # SHORT는 음수
                    else:  # LONG
                        position_amt = abs(contracts)   # LONG은 양수
                    
                    # 실제 레버리지 정보 가져오기 (바이낸스 API 직접 호출)
                    symbol_clean = pos['symbol'].replace('/', '')
                    actual_leverage = await self._get_symbol_leverage(symbol_clean)
                    
                    formatted_pos = {
                        'symbol': symbol_clean,
                        'positionAmt': position_amt,
                        'entryPrice': pos['entryPrice'] or 0,
                        'markPrice': pos['markPrice'] or 0,
                        'unRealizedProfit': pos['unrealizedPnl'] or 0,
                        'initialMargin': pos['initialMargin'] or 0,
                        'leverage': actual_leverage,  # 실제 레버리지 사용
                        'side': side  # 명시적으로 side 추가
                    }
                    formatted_positions.append(formatted_pos)
                    
                    print(f"CCXT Position: {pos['symbol']} side={side} contracts={contracts} amt={position_amt} leverage={actual_leverage}")
            
            return formatted_positions
            
        except Exception as e:
            print(f"CCXT 포지션 조회 오류: {e}")
            return []
    
    async def _get_symbol_leverage(self, symbol):
        """특정 심볼의 실제 레버리지 조회"""
        try:
            # 바이낸스 선물 API를 직접 호출하여 레버리지 정보 가져오기
            response = await self.exchange.fapiPrivateGetPositionRisk({
                'symbol': symbol
            })
            
            if response and len(response) > 0:
                leverage = float(response[0].get('leverage', 1))
                print(f"심볼 {symbol}의 실제 레버리지: {leverage}")
                return leverage
            else:
                print(f"심볼 {symbol}의 레버리지 정보를 찾을 수 없음")
                return 1
                
        except Exception as e:
            print(f"레버리지 조회 오류 ({symbol}): {e}")
            # 기본값으로 CCXT에서 제공하는 값 사용
            try:
                positions = await self.exchange.fetch_positions([symbol])
                if positions and len(positions) > 0:
                    return positions[0].get('leverage', 1)
            except:
                pass
            return 1
    
    async def get_open_orders(self, symbol=None):
        """미체결 주문 조회"""
        try:
            if symbol:
                # 심볼 형태 변환 (BTCUSDT -> BTC/USDT)
                if '/' not in symbol:
                    symbol = symbol[:-4] + '/' + symbol[-4:]
                return await self.exchange.fetch_open_orders(symbol)
            else:
                return await self.exchange.fetch_open_orders()
        except Exception as e:
            print(f"CCXT 미체결 주문 조회 오류: {e}")
            return []
    
    async def get_trade_history(self, symbol, start_time=None, end_time=None, limit=50):
        """거래 내역 조회"""
        try:
            # 심볼 형태 변환
            if '/' not in symbol:
                symbol = symbol[:-4] + '/' + symbol[-4:]
                
            params = {'limit': limit}
            if start_time:
                params['startTime'] = start_time
            if end_time:
                params['endTime'] = end_time
                
            trades = await self.exchange.fetch_my_trades(symbol, params=params)
            
            # CCXT 형태를 바이낸스 API 형태로 변환
            formatted_trades = []
            for trade in trades:
                formatted_trade = {
                    'time': trade['timestamp'],
                    'symbol': trade['symbol'].replace('/', ''),
                    'side': trade['side'].upper(),
                    'qty': trade['amount'],
                    'price': trade['price'],
                    'quoteQty': trade['cost'],
                    'commission': trade['fee']['cost'] if trade['fee'] else 0,
                    'realizedPnl': 0,  # CCXT에서 직접 제공하지 않음
                    'orderId': trade['order']
                }
                formatted_trades.append(formatted_trade)
                
            return formatted_trades
            
        except Exception as e:
            print(f"CCXT 거래내역 조회 오류: {e}")
            return []
    
    async def place_order(self, symbol, side, order_type, quantity, price=None, leverage=None):
        """주문 실행"""
        try:
            # 레버리지 설정
            if leverage:
                await self.set_leverage(symbol, leverage)
            
            # 심볼 형태 변환
            if '/' not in symbol:
                symbol = symbol[:-4] + '/' + symbol[-4:]
            
            # 주문 실행
            if order_type.upper() == 'MARKET':
                result = await self.exchange.create_market_order(
                    symbol, side.lower(), quantity
                )
            else:  # LIMIT
                result = await self.exchange.create_limit_order(
                    symbol, side.lower(), quantity, price
                )
            
            # 바이낸스 API 형태로 변환
            return {
                'orderId': result['id'],
                'symbol': result['symbol'].replace('/', ''),
                'status': result['status'],
                'side': result['side'].upper(),
                'type': result['type'].upper(),
                'origQty': result['amount'],
                'price': result['price']
            }
            
        except Exception as e:
            print(f"CCXT 주문 실행 오류: {e}")
            return None
    
    async def cancel_order(self, symbol, order_id):
        """주문 취소"""
        try:
            # 심볼 형태 변환
            if '/' not in symbol:
                symbol = symbol[:-4] + '/' + symbol[-4:]
                
            result = await self.exchange.cancel_order(order_id, symbol)
            return result
            
        except Exception as e:
            print(f"CCXT 주문 취소 오류: {e}")
            return None
    
    async def set_leverage(self, symbol, leverage):
        """레버리지 설정"""
        try:
            # 심볼 형태 변환
            if '/' not in symbol:
                symbol = symbol[:-4] + '/' + symbol[-4:]
                
            await self.exchange.set_leverage(leverage, symbol)
            print(f"레버리지 설정 완료: {symbol} -> {leverage}x")
            return True
            
        except Exception as e:
            print(f"CCXT 레버리지 설정 오류: {e}")
            return False
    
    async def get_orderbook(self, symbol, limit=20):
        """호가창 조회"""
        try:
            # 심볼 형태 변환
            if '/' not in symbol:
                symbol = symbol[:-4] + '/' + symbol[-4:]
                
            orderbook = await self.exchange.fetch_order_book(symbol, limit)
            
            # 바이낸스 API 형태로 변환
            return {
                'bids': orderbook['bids'],
                'asks': orderbook['asks']
            }
            
        except Exception as e:
            print(f"CCXT 호가창 조회 오류: {e}")
            return None
    
    async def get_ticker_price(self, symbol):
        """현재가 조회"""
        try:
            # 심볼 형태 변환
            if '/' not in symbol:
                symbol = symbol[:-4] + '/' + symbol[-4:]
                
            ticker = await self.exchange.fetch_ticker(symbol)
            
            return {
                'symbol': symbol.replace('/', ''),
                'price': ticker['last']
            }
            
        except Exception as e:
            print(f"CCXT 현재가 조회 오류: {e}")
            return None
    
    async def get_24hr_ticker(self, symbol):
        """24시간 통계"""
        try:
            # 심볼 형태 변환
            if '/' not in symbol:
                symbol = symbol[:-4] + '/' + symbol[-4:]
                
            ticker = await self.exchange.fetch_ticker(symbol)
            
            return {
                'symbol': symbol.replace('/', ''),
                'lastPrice': ticker['last'],
                'priceChange': ticker['change'],
                'priceChangePercent': ticker['percentage'],
                'volume': ticker['baseVolume'],
                'quoteVolume': ticker['quoteVolume']
            }
            
        except Exception as e:
            print(f"CCXT 24시간 통계 조회 오류: {e}")
            return None
    
    def calculate_quantity(self, usdt_amount, price, leverage=1):
        """USDT 금액으로 수량 계산"""
        try:
            quantity = Decimal(str(usdt_amount)) * Decimal(str(leverage)) / Decimal(str(price))
            return float(quantity.quantize(Decimal('0.001'), rounding=ROUND_DOWN))
        except:
            return 0
    
    async def close(self):
        """연결 종료"""
        try:
            await self.exchange.close()
            print("CCXT 거래소 연결이 종료되었습니다.")
        except Exception as e:
            print(f"CCXT 연결 종료 중 오류: {e}")