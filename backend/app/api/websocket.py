from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.engine import engine

logger = logging.getLogger(__name__)
router = APIRouter()


async def _safe_send(websocket: WebSocket, payload: dict | object) -> None:
    if websocket.client_state != WebSocketState.CONNECTED:
        raise WebSocketDisconnect()
    text = json.dumps(payload, ensure_ascii=False, default=str)
    await websocket.send_text(text)


@router.websocket("/ws/realtime")
async def realtime_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = engine.subscribe()
    try:
        if engine._latest:
            await _safe_send(
                websocket, engine._latest.model_dump(mode="json")
            )
        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=30.0)
                await _safe_send(websocket, data)
            except asyncio.TimeoutError:
                await _safe_send(websocket, {"type": "ping"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("websocket closed: %s", e)
    finally:
        engine.unsubscribe(queue)
