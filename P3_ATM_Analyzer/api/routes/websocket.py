from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...database import fetch_records, fetch_upload, get_connection
from ...services.realtime import manager

router = APIRouter(tags=["realtime"])


def _build_snapshot(upload_id: int) -> dict[str, object]:
    with get_connection() as db:
        upload = fetch_upload(db, upload_id)
        if upload is None:
            return {"type": "error", "message": "Upload not found"}

        records = fetch_records(db, upload_id, limit=50, offset=0)
        geo_records = [record for record in records if record["latitude"] is not None and record["longitude"] is not None]

        return {
            "type": "snapshot",
            "upload_id": upload_id,
            "filename": upload["filename"],
            "row_count": upload["row_count"],
            "has_geo": upload["has_geo"],
            "geo_records": geo_records,
        }


@router.websocket("/ws/datasets/{upload_id}")
async def dataset_socket(websocket: WebSocket, upload_id: int) -> None:
    await manager.connect(upload_id, websocket)
    try:
        await websocket.send_json(_build_snapshot(upload_id))
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")

            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if message_type == "refresh":
                await websocket.send_json(_build_snapshot(upload_id))
                continue

            await websocket.send_json({"type": "error", "message": "Unknown message type"})
    except WebSocketDisconnect:
        manager.disconnect(upload_id, websocket)