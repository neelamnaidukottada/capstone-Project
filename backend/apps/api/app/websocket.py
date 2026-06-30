"""Campaign WebSocket manager with room-based broadcast and heartbeat."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from time import monotonic
from typing import Any
from uuid import UUID

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


class WebSocketEventType(StrEnum):
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    OPTIMIZATION_ALERT = "optimization_alert"
    CAMPAIGN_COMPLETED = "campaign_completed"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    CONNECTED = "connected"


@dataclass
class ConnectionContext:
    websocket: WebSocket
    campaign_id: str
    user_id: str
    last_pong_at: float
    last_message_at: float
    connected_at: float


class CampaignWebSocketManager:
    """Manages campaign-specific websocket rooms and event broadcast."""

    def __init__(self) -> None:
        self._rooms: dict[str, dict[int, ConnectionContext]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, campaign_id: UUID | str, user_id: str) -> ConnectionContext:
        await websocket.accept()
        room_key = str(campaign_id)
        now = monotonic()
        conn = ConnectionContext(
            websocket=websocket,
            campaign_id=room_key,
            user_id=user_id,
            last_pong_at=now,
            last_message_at=0.0,
            connected_at=now,
        )

        async with self._lock:
            self._rooms.setdefault(room_key, {})[id(websocket)] = conn

        await self.send_personal(
            conn,
            WebSocketEventType.CONNECTED,
            {
                "campaign_id": room_key,
                "message": "Connected to campaign stream",
            },
        )
        logger.info("ws_connected", campaign_id=room_key, user_id=user_id)
        return conn

    async def disconnect(self, conn: ConnectionContext) -> None:
        async with self._lock:
            room = self._rooms.get(conn.campaign_id, {})
            room.pop(id(conn.websocket), None)
            if not room:
                self._rooms.pop(conn.campaign_id, None)
        logger.info("ws_disconnected", campaign_id=conn.campaign_id, user_id=conn.user_id)

    async def send_personal(
        self,
        conn: ConnectionContext,
        event_type: WebSocketEventType,
        payload: dict[str, Any],
    ) -> None:
        await conn.websocket.send_json(self._build_event(event_type, payload))

    async def broadcast(
        self,
        campaign_id: UUID | str,
        event_type: WebSocketEventType,
        payload: dict[str, Any],
    ) -> None:
        room_key = str(campaign_id)
        message = self._build_event(event_type, payload)

        async with self._lock:
            connections = list(self._rooms.get(room_key, {}).values())

        if not connections:
            return

        for conn in connections:
            try:
                await conn.websocket.send_json(message)
            except Exception as exc:
                logger.warning(
                    "ws_broadcast_failed",
                    campaign_id=room_key,
                    user_id=conn.user_id,
                    error=str(exc),
                )

    async def handle_client_message(self, conn: ConnectionContext, raw_message: str) -> None:
        now = monotonic()
        # Max 1 message/second per client.
        if conn.last_message_at and (now - conn.last_message_at) < 1.0:
            await self.send_personal(
                conn,
                WebSocketEventType.ERROR,
                {
                    "agent_name": "websocket_gateway",
                    "error_message": "Rate limit exceeded: max 1 message/second",
                    "retry_count": 0,
                },
            )
            return

        conn.last_message_at = now

        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            await self.send_personal(
                conn,
                WebSocketEventType.ERROR,
                {
                    "agent_name": "websocket_gateway",
                    "error_message": "Invalid JSON payload",
                    "retry_count": 0,
                },
            )
            return

        message_type = payload.get("type")
        if message_type == WebSocketEventType.PONG:
            conn.last_pong_at = monotonic()
            return

        if message_type == WebSocketEventType.PING:
            await self.send_personal(conn, WebSocketEventType.PONG, {"timestamp": self._ts()})
            return

        # Unsupported client messages are acknowledged with error for observability.
        await self.send_personal(
            conn,
            WebSocketEventType.ERROR,
            {
                "agent_name": "websocket_gateway",
                "error_message": f"Unsupported message type: {message_type}",
                "retry_count": 0,
            },
        )

    async def heartbeat(
        self,
        conn: ConnectionContext,
        *,
        interval_seconds: float = 15.0,
        timeout_seconds: float = 45.0,
    ) -> None:
        """Ping client periodically and close stale connections."""
        while True:
            await asyncio.sleep(interval_seconds)
            idle_for = monotonic() - conn.last_pong_at
            if idle_for > timeout_seconds:
                await self.send_personal(
                    conn,
                    WebSocketEventType.ERROR,
                    {
                        "agent_name": "websocket_gateway",
                        "error_message": "Heartbeat timeout",
                        "retry_count": 0,
                    },
                )
                await conn.websocket.close(code=1001, reason="Heartbeat timeout")
                return

            await self.send_personal(conn, WebSocketEventType.PING, {"timestamp": self._ts()})

    def _build_event(self, event_type: WebSocketEventType, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "event": event_type,
            "timestamp": self._ts(),
            **payload,
        }

    @staticmethod
    def _ts() -> str:
        return datetime.now(UTC).isoformat()


websocket_manager = CampaignWebSocketManager()
