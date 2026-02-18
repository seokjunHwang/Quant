import json
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    """WebSocket connection manager with room-based broadcasting."""

    def __init__(self):
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, room: str) -> None:
        await websocket.accept()
        self._rooms[room].add(websocket)

    def disconnect(self, websocket: WebSocket, room: str) -> None:
        self._rooms[room].discard(websocket)
        if not self._rooms[room]:
            del self._rooms[room]

    async def broadcast(self, room: str, data: dict) -> None:
        message = json.dumps(data, default=str)
        dead: list[WebSocket] = []
        for ws in self._rooms.get(room, set()):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._rooms[room].discard(ws)

    async def send_personal(self, websocket: WebSocket, data: dict) -> None:
        await websocket.send_json(data)

    @property
    def active_rooms(self) -> list[str]:
        return list(self._rooms.keys())

    def room_count(self, room: str) -> int:
        return len(self._rooms.get(room, set()))


manager = ConnectionManager()
