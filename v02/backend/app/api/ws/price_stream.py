from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.websocket_manager import manager

router = APIRouter()


@router.websocket("/price/{symbol}")
async def price_websocket(websocket: WebSocket, symbol: str):
    """실시간 가격 스트림. Binance WebSocket → 클라이언트 fan-out."""
    room = f"price:{symbol.upper()}"
    await manager.connect(websocket, room)
    try:
        while True:
            # 클라이언트 heartbeat 수신 (ping/pong)
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, room)
