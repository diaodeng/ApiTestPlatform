# app/pressure/api/ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from module_pressure.ws.manager import ws_manager

router = APIRouter()

@router.websocket("/ws/pressure/{job_id}")
async def pressure_ws(ws: WebSocket, job_id: int):
    await ws_manager.connect(job_id, ws)
    try:
        while True:
            await ws.receive_text()  # 心跳占位
    except WebSocketDisconnect:
        ws_manager.disconnect(job_id, ws)
