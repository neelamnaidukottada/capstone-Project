from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.core.config import settings
from app.services.campaign_service import store
from main import create_app


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest.fixture()
def client(app):
    return TestClient(app, base_url="http://localhost")


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    payload = {
        "sub": "test-user",
        "role": "admin",
        "organization_id": "org-test",
        "email": "test@example.com",
        "token_type": "access",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, settings.API_SECRET_KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def manager_headers() -> dict[str, str]:
    payload = {
        "sub": "manager-user",
        "role": "manager",
        "organization_id": "org-test",
        "email": "manager@example.com",
        "token_type": "access",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, settings.API_SECRET_KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def viewer_headers() -> dict[str, str]:
    payload = {
        "sub": "viewer-user",
        "role": "viewer",
        "organization_id": "org-test",
        "email": "viewer@example.com",
        "token_type": "access",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, settings.API_SECRET_KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def campaign_id(manager_headers):
    payload = {
        "goal": {
            "goal": "Increase SQL pipeline by 20%",
            "budget": 50000,
            "timeline_days": 60,
            "industry": "B2B SaaS",
            "product_description": "Autonomous campaign manager",
        },
        "human_in_the_loop": True,
        "auto_approve": False,
    }
    record = asyncio.run(store.create_campaign("manager-user", "org-test", payload))
    return str(record.id)


@pytest.fixture(autouse=True)
def cleanup_store():
    yield
    store._campaigns.clear()  # pylint: disable=protected-access
