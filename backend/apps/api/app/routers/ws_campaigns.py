"""WebSocket endpoints for real-time campaign updates."""
from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_token
from app.core.logging import get_logger
from app.services.campaign_service import store
from app.websocket import websocket_manager

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws/campaigns/{campaign_id}")
async def campaign_updates_ws(websocket: WebSocket, campaign_id: UUID):
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4401, reason="Missing JWT token")
        return

    try:
        claims = decode_token(token)
    except Exception:
        await websocket.close(code=4401, reason="Invalid JWT token")
        return

    user_id = str(claims.get("sub", "unknown"))
    user_org = str(claims.get("organization_id") or "")

    try:
        campaign = await store.get_campaign(campaign_id)
    except Exception:
        await websocket.close(code=4404, reason="Campaign not found")
        return

    if not user_org or campaign.organization_id != user_org:
        await websocket.close(code=4403, reason="Forbidden")
        return

    conn = await websocket_manager.connect(websocket, campaign_id, user_id)
    heartbeat_task = asyncio.create_task(websocket_manager.heartbeat(conn))

    try:
        while True:
            raw_message = await websocket.receive_text()
            await websocket_manager.handle_client_message(conn, raw_message)
    except WebSocketDisconnect:
        logger.info("websocket_disconnected", campaign_id=str(campaign_id))
    finally:
        heartbeat_task.cancel()
        await websocket_manager.disconnect(conn)
