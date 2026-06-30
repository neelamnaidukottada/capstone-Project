from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.services.campaign_service import store


def _ws_token(sub: str, org_id: str) -> str:
    payload = {
        "sub": sub,
        "role": "manager",
        "organization_id": org_id,
        "email": "ws@example.com",
        "token_type": "access",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=15),
    }
    return jwt.encode(payload, settings.API_SECRET_KEY, algorithm="HS256")


def test_websocket_connect_and_receive_connected_event(client):
    record = asyncio.run(
        store.create_campaign(
            user_id="ws-user",
            organization_id="org-ws",
            payload={
                "goal": {
                    "goal": "Grow pipeline",
                    "budget": 10000,
                    "timeline_days": 30,
                    "industry": "SaaS",
                    "product_description": "Platform",
                }
            },
        )
    )

    token = _ws_token("ws-user", "org-ws")
    with client.websocket_connect(
        f"/ws/campaigns/{record.id}?token={token}",
        headers={"host": "localhost"},
    ) as websocket:
        first = websocket.receive_json()
        assert first["event"] == "connected"
        assert first["campaign_id"] == str(record.id)


def test_websocket_forbidden_for_other_org(client):
    record = asyncio.run(
        store.create_campaign(
            user_id="owner-user",
            organization_id="org-a",
            payload={
                "goal": {
                    "goal": "Grow pipeline",
                    "budget": 10000,
                    "timeline_days": 30,
                    "industry": "SaaS",
                    "product_description": "Platform",
                }
            },
        )
    )

    token = _ws_token("other-user", "org-b")
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/ws/campaigns/{record.id}?token={token}",
            headers={"host": "localhost"},
        ):
            pass
