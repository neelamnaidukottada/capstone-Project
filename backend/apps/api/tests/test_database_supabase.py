from __future__ import annotations

import os

import pytest
from supabase import create_client


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("TEST_SUPABASE_URL") or not os.getenv("TEST_SUPABASE_SERVICE_ROLE_KEY"),
    reason="TEST_SUPABASE_URL / TEST_SUPABASE_SERVICE_ROLE_KEY are not configured",
)
def test_supabase_test_instance_read_write():
    client = create_client(
        os.environ["TEST_SUPABASE_URL"],
        os.environ["TEST_SUPABASE_SERVICE_ROLE_KEY"],
    )

    org_name = "pytest-org"
    created = client.table("app_organizations").insert({"name": org_name}).execute()
    assert created.data

    org_id = created.data[0]["id"]
    fetched = client.table("app_organizations").select("id,name").eq("id", org_id).single().execute()
    assert fetched.data["name"] == org_name

    client.table("app_organizations").delete().eq("id", org_id).execute()
