from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, upload_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[upload_id].add(websocket)

    def disconnect(self, upload_id: int, websocket: WebSocket) -> None:
        self._connections[upload_id].discard(websocket)
        if not self._connections[upload_id]:
            self._connections.pop(upload_id, None)

    async def send_to_upload(self, upload_id: int, payload: dict[str, Any]) -> None:
        for websocket in list(self._connections.get(upload_id, set())):
            await websocket.send_json(payload)


manager = WebSocketManager()