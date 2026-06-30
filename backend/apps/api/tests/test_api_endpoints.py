from __future__ import annotations

import asyncio
from uuid import UUID

from app.services.campaign_service import CampaignStore, store


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_campaign_requires_manager_role(client, viewer_headers):
    response = client.post(
        "/api/v1/campaigns",
        headers=viewer_headers,
        json={
            "goal": {
                "goal": "Grow leads",
                "budget": 10000,
                "timeline_days": 30,
                "industry": "SaaS",
                "product_description": "Tool",
            }
        },
    )
    assert response.status_code == 403


def test_create_and_fetch_campaign(client, manager_headers, monkeypatch):
    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.routers.campaigns.execute_workflow", _noop)
    monkeypatch.setattr(store, "_db_available", False)

    create = client.post(
        "/api/v1/campaigns",
        headers=manager_headers,
        json={
            "campaign_name": "Resume Builder Launch",
            "goal": {
                "goal": "Increase qualified pipeline by 20%",
                "budget": 25000,
                "timeline_days": 45,
                "target_audience": "Software Engineers",
                "industry": "SaaS",
                "product_description": "Automation platform",
            },
            "human_in_the_loop": True,
            "auto_approve": False,
        },
    )

    assert create.status_code == 200
    cid = create.json()["campaign_id"]

    get_one = client.get(f"/api/v1/campaigns/{cid}", headers=manager_headers)
    assert get_one.status_code == 200
    assert get_one.json()["campaign_id"] == cid

    listing = client.get("/api/v1/campaigns?limit=50&offset=0", headers=manager_headers)
    assert listing.status_code == 200
    created_item = next((item for item in listing.json()["campaigns"] if item["campaign_id"] == cid), None)
    assert created_item is not None
    assert created_item["name"] == "Resume Builder Launch"
    assert created_item["budget_total"] == 25000

    record = asyncio.run(store.get_campaign(UUID(cid)))
    assert record.goal.get("target_audience") == "Software Engineers"


def test_report_generation_trigger_when_missing(client, manager_headers):
    payload = {
        "goal": {
            "goal": "Increase SQL pipeline by 15%",
            "budget": 35000,
            "timeline_days": 40,
            "industry": "Fintech",
            "product_description": "B2B growth product",
        }
    }
    record = asyncio.run(store.create_campaign("manager-user", "org-test", payload))

    response = client.get(f"/api/v1/campaigns/{record.id}/report?format=json", headers=manager_headers)
    assert response.status_code == 409


def test_delete_campaign_removes_record(client, manager_headers, monkeypatch):
    monkeypatch.setattr(store, "_db_available", False)
    payload = {
        "goal": {
            "goal": "Delete me campaign",
            "budget": 5000,
            "timeline_days": 14,
            "industry": "SaaS",
            "product_description": "Temporary campaign",
        }
    }
    record = asyncio.run(store.create_campaign("manager-user", "org-test", payload))

    response = client.delete(f"/api/v1/campaigns/{record.id}", headers=manager_headers)
    assert response.status_code == 200
    assert response.json()["campaign_id"] == str(record.id)

    missing = client.get(f"/api/v1/campaigns/{record.id}", headers=manager_headers)
    assert missing.status_code == 404


def test_campaigns_survive_restart_with_local_snapshot(monkeypatch, tmp_path):
    snapshot = tmp_path / "campaign_store.json"
    monkeypatch.setattr(store, "_db_available", False)
    monkeypatch.setattr(store, "_snapshot_path", snapshot)
    store._campaigns.clear()  # pylint: disable=protected-access
    store._subscribers.clear()  # pylint: disable=protected-access

    payload = {
        "campaign_name": "Persistent Campaign",
        "goal": {
            "goal": "Persist campaigns across restart",
            "budget": 12000,
            "timeline_days": 20,
            "industry": "SaaS",
            "product_description": "Persistence validation campaign",
        },
        "human_in_the_loop": True,
        "auto_approve": False,
    }
    created = asyncio.run(store.create_campaign("manager-user", "org-test", payload))
    assert snapshot.exists()

    restarted = CampaignStore()
    monkeypatch.setattr(restarted, "_db_available", False)
    monkeypatch.setattr(restarted, "_snapshot_path", snapshot)
    restarted._campaigns.clear()  # pylint: disable=protected-access
    restarted._load_local_snapshot()  # pylint: disable=protected-access

    loaded = asyncio.run(restarted.get_campaign(created.id))
    assert loaded.id == created.id
    assert loaded.name == "Persistent Campaign"
