from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.websocket_manager import manager

router = APIRouter()


@router.websocket("/signals")
async def signal_websocket(websocket: WebSocket):
    """AI 시그널 실시간 스트림."""
    room = "signals:all"
    await manager.connect(websocket, room)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, room)
