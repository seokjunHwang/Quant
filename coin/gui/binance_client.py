import asyncio
import json
import hmac
import hashlib
import time
import os
from urllib.parse import urlencode
import aiohttp
import websockets
from decimal import Decimal, ROUND_DOWN

class BinanceClient:
    def __init__(self, api_key, secret_key, testnet=True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.testnet = testnet
        
        if testnet:
            self.base_url = "https://testnet.binancefuture.com"
            self.ws_url = "wss://stream.binancefuture.com"
        else:
            self.base_url = "https://fapi.binance.com"
            self.ws_url = "wss://fstream.binance.com"
            
        self.session = None
        self.ws_connection = None
        
    def _generate_signature(self, params):
        """API 서명 생성"""
        query_string = urlencode(params)
        return hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def _make_request(self, method, endpoint, params=None, signed=False):
        """API 요청 실행"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        url = f"{self.base_url}{endpoint}"
        headers = {"X-MBX-APIKEY": self.api_key}
        
        if params is None:
            params = {}
            
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)
            
        try:
            if method == "GET":
                async with self.session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        print(f"❌ API 에러 [{endpoint}]: {response.status} - {text}")
                        return None
                    return await response.json()
                    
            elif method == "POST":
                async with self.session.post(url, data=params, headers=headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        print(f"❌ API 에러 [{endpoint}]: {response.status} - {text}")
                        return None
                    return await response.json()
                    
            elif method == "DELETE":
                async with self.session.delete(url, data=params, headers=headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        print(f"❌ API 에러 [{endpoint}]: {response.status} - {text}")
                        return None
                    return await response.json()
                    
        except Exception as e:
            print(f"❌ 요청 실패 [{endpoint}]: {e}")
            return None

    async def get_account_info(self):
        """계좌 정보 조회"""
        return await self._make_request("GET", "/fapi/v2/account", signed=True)
    
    async def get_balance(self):
        """잔고 조회"""
        return await self._make_request("GET", "/fapi/v2/balance", signed=True)
    
    async def get_positions(self):
        """포지션 정보 조회"""
        positions = await self._make_request("GET", "/fapi/v2/positionRisk", signed=True)
        
        if not positions:
            return []
        
        # 활성 포지션만 필터링
        active_positions = []
        for pos in positions:
            position_amt = float(pos.get('positionAmt', 0))
            if position_amt != 0:
                active_positions.append(pos)
        
        return active_positions
    
    async def get_open_orders(self, symbol=None):
        """미체결 주문 조회"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        orders = await self._make_request("GET", "/fapi/v1/openOrders", params, signed=True)
        return orders or []
    
    async def get_trade_history(self, symbol, start_time=None, end_time=None, limit=50):
        """거래 내역 조회"""
        params = {
            'symbol': symbol,
            'limit': limit
        }
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
            
        return await self._make_request("GET", "/fapi/v1/userTrades", params, signed=True)
    
    async def place_order(self, symbol, side, order_type, quantity, price=None, leverage=None):
        """주문 실행"""
        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': str(quantity)
        }
        
        if price and order_type == 'LIMIT':
            params['price'] = str(price)
            params['timeInForce'] = 'GTC'
            
        if leverage:
            await self.set_leverage(symbol, leverage)
            
        return await self._make_request("POST", "/fapi/v1/order", params, signed=True)
    
    async def cancel_order(self, symbol, order_id):
        """주문 취소"""
        params = {
            'symbol': symbol,
            'orderId': int(order_id)
        }
        return await self._make_request("DELETE", "/fapi/v1/order", params, signed=True)
    
    async def set_leverage(self, symbol, leverage):
        """레버리지 설정"""
        params = {
            'symbol': symbol,
            'leverage': int(leverage)
        }
        return await self._make_request("POST", "/fapi/v1/leverage", params, signed=True)
        
    async def get_order(self, symbol, order_id):
        """특정 주문 정보 조회"""
        try:
            params = {
                'symbol': symbol,
                'orderId': order_id
            }
            return await self._make_request("GET", "/fapi/v1/order", params, signed=True)
        except Exception as e:
            print(f"❌ 주문 조회 실패: {e}")
            return None

    async def get_orderbook(self, symbol, limit=20):
        """호가창 조회"""
        params = {
            'symbol': symbol,
            'limit': limit
        }
        return await self._make_request("GET", "/fapi/v1/depth", params)
    
    async def get_ticker_price(self, symbol):
        """현재가 조회"""
        params = {'symbol': symbol}
        return await self._make_request("GET", "/fapi/v1/ticker/price", params)
    
    async def get_ticker(self, symbol):
        """티커 정보 조회"""
        params = {'symbol': symbol}
        result = await self._make_request("GET", "/fapi/v1/ticker/24hr", params)
        if result:
            return {'last': result.get('lastPrice', '0')}
        return None
    
    async def get_24hr_ticker(self, symbol):
        """24시간 통계"""
        params = {'symbol': symbol}
        return await self._make_request("GET", "/fapi/v1/ticker/24hr", params)
    
    def calculate_quantity(self, usdt_amount, price, leverage=1):
        """USDT 금액으로 수량 계산"""
        try:
            raw_quantity = Decimal(str(usdt_amount)) * Decimal(str(leverage)) / Decimal(str(price))
            quantity = float(raw_quantity.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
            
            if quantity < 0.000001:
                quantity = 0.000001
                
            return quantity
            
        except Exception as e:
            print(f"❌ 수량 계산 실패: {e}")
            return 0
    
    async def start_websocket(self, symbol, callback):
        """웹소켓 스트림 시작"""
        try:
            stream_name = f"{symbol.lower()}@ticker"
            ws_url = f"{self.ws_url}/ws/{stream_name}"
            
            async with websockets.connect(ws_url) as websocket:
                self.ws_connection = websocket
                async for message in websocket:
                    data = json.loads(message)
                    if callback:
                        callback(data)
                        
        except Exception as e:
            print(f"❌ 웹소켓 오류: {e}")
    
    async def get_symbol_info(self, symbol):
        """심볼 정보 조회"""
        try:
            exchange_info = await self._make_request("GET", "/fapi/v1/exchangeInfo")
            
            if exchange_info and 'symbols' in exchange_info:
                for symbol_info in exchange_info['symbols']:
                    if symbol_info['symbol'] == symbol:
                        filters = {f['filterType']: f for f in symbol_info['filters']}
                        
                        result = {
                            'symbol': symbol,
                            'status': symbol_info['status'],
                            'pricePrecision': symbol_info.get('pricePrecision', 2),
                            'quantityPrecision': symbol_info.get('quantityPrecision', 3),
                            'baseAssetPrecision': symbol_info.get('baseAssetPrecision', 8),
                            'quotePrecision': symbol_info.get('quotePrecision', 8),
                        }
                        
                        if 'LOT_SIZE' in filters:
                            result['minQty'] = float(filters['LOT_SIZE']['minQty'])
                            result['maxQty'] = float(filters['LOT_SIZE']['maxQty'])
                            result['stepSize'] = float(filters['LOT_SIZE']['stepSize'])
                        
                        if 'PRICE_FILTER' in filters:
                            result['minPrice'] = float(filters['PRICE_FILTER']['minPrice'])
                            result['maxPrice'] = float(filters['PRICE_FILTER']['maxPrice'])
                            result['tickSize'] = float(filters['PRICE_FILTER']['tickSize'])
                        
                        if 'MIN_NOTIONAL' in filters:
                            result['minNotional'] = float(filters['MIN_NOTIONAL']['notional'])
                        
                        return result
                        
            return None
            
        except Exception as e:
            print(f"❌ 심볼 정보 조회 실패: {e}")
            return None

    async def get_position_by_symbol(self, symbol):
        """특정 심볼의 포지션 정보만 조회"""
        try:
            positions = await self.get_positions()
            
            for pos in positions:
                if pos.get('symbol') == symbol:
                    position_amt = float(pos.get('positionAmt', 0))
                    if position_amt != 0:
                        return pos
            
            return None
            
        except Exception as e:
            print(f"❌ {symbol} 포지션 조회 실패: {e}")
            return None

    async def close_position_market(self, symbol):
        """시장가로 포지션 전량 청산"""
        try:
            position = await self.get_position_by_symbol(symbol)
            
            if not position:
                return None
            
            position_amt = float(position.get('positionAmt', 0))
            
            if position_amt > 0:
                side = 'SELL'
                quantity = abs(position_amt)
            else:
                side = 'BUY'
                quantity = abs(position_amt)
            
            try:
                from strategy_widget import adjust_quantity_precision
                adjusted_quantity = adjust_quantity_precision(symbol, quantity)
            except:
                adjusted_quantity = round(quantity, 3)
            
            return await self.place_order(
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=adjusted_quantity
            )
            
        except Exception as e:
            print(f"❌ {symbol} 청산 실패: {e}")
            return None

    async def close(self):
        """세션 안전하게 종료"""
        try:
            if self.session and not self.session.closed:
                await self.session.close()
        except:
            pass