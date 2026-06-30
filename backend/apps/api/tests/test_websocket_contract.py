from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.services import campaign_service
from app.websocket import WebSocketEventType, websocket_manager


CONTRACT_PATH = Path(__file__).resolve().parents[4] / "frontend" / "apps" / "web" / "src" / "lib" / "websocket-contract.json"


def _load_contract() -> dict[str, list[str]]:
    with CONTRACT_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _assert_contract_fields(message: dict[str, object], contract: dict[str, list[str]]) -> None:
    event_name = str(message["event"])
    required_keys = contract[event_name]
    missing = [key for key in required_keys if key not in message]
    assert not missing, f"Missing keys for {event_name}: {missing}"


@pytest.mark.asyncio
async def test_workflow_deps_emit_payloads_matching_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    contract = _load_contract()
    captured: list[dict[str, object]] = []

    async def fake_broadcast(_campaign_id: object, event_type: WebSocketEventType, payload: dict[str, object]) -> None:
        captured.append({"event": event_type.value, "timestamp": "2026-01-01T00:00:00Z", **payload})

    monkeypatch.setattr(campaign_service.websocket_manager, "broadcast", fake_broadcast)

    deps = await campaign_service._workflow_deps(uuid4())
    await deps["planner"]({"campaign_goal": {"goal": "Grow pipeline", "budget": 10000}, "total_budget": 10000})
    await deps["content_creator"]({})
    await deps["media_buyer"]({"total_budget": 10000})
    await deps["performance_analyst"]({})
    await deps["reporter"]({})

    assert captured, "Expected workflow deps to emit websocket events"

    for message in captured:
        _assert_contract_fields(message, contract)


@pytest.mark.asyncio
async def test_gateway_payloads_match_contract() -> None:
    contract = _load_contract()
    sample_payloads: list[tuple[WebSocketEventType, dict[str, object]]] = [
        (
            WebSocketEventType.HUMAN_APPROVAL_REQUIRED,
            {"step": "strategy", "payload": {"type": "strategy"}, "timeout": 600},
        ),
        (
            WebSocketEventType.CAMPAIGN_COMPLETED,
            {"campaign_id": str(uuid4()), "report_url": "/api/v1/campaigns/demo/report?format=json"},
        ),
        (
            WebSocketEventType.ERROR,
            {"agent_name": "supervisor", "error_message": "workflow failed", "retry_count": 1},
        ),
        (WebSocketEventType.PING, {}),
        (WebSocketEventType.PONG, {}),
        (
            WebSocketEventType.CONNECTED,
            {"campaign_id": str(uuid4()), "message": "Connected to campaign stream"},
        ),
    ]

    for event_type, payload in sample_payloads:
        message = websocket_manager._build_event(event_type, payload)
        _assert_contract_fields(message, contract)
