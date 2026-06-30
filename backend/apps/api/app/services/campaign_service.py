"""Campaign orchestration service with in-memory persistence and websocket pub-sub."""
from __future__ import annotations

import asyncio
import base64
import copy
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.core.logging import get_logger
from app.core.supabase_client import get_supabase_admin_client
from app.websocket import WebSocketEventType, websocket_manager

logger = get_logger(__name__)


@dataclass
class CampaignRecord:
    id: UUID
    user_id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime
    status: str
    current_agent: str | None
    progress_percentage: int
    estimated_completion: datetime | None
    goal: dict[str, Any]
    content_request: str | None = None
    qa_execution_data: dict[str, Any] | None = None
    name: str | None = None
    strategy: dict[str, Any] | None = None
    content: dict[str, Any] | None = None
    media_plan: dict[str, Any] | None = None
    performance: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    error: str | None = None
    pending_approval: dict[str, Any] | None = None
    approvals: dict[str, bool] = field(default_factory=lambda: {"strategy": False, "media_plan": False})
    human_in_the_loop: bool = True
    auto_approve: bool = False


class CampaignStore:
    def __init__(self) -> None:
        self._campaigns: dict[UUID, CampaignRecord] = {}
        self._lock = asyncio.Lock()
        self._subscribers: dict[UUID, list[asyncio.Queue[dict[str, Any]]]] = {}
        self._admin = None
        self._db_available = True
        self._campaign_columns: dict[str, bool] = {}
        self._snapshot_path = Path(__file__).resolve().parents[2] / ".campaign_store.json"
        self._load_local_snapshot()

    def _record_to_snapshot(self, record: CampaignRecord) -> dict[str, Any]:
        return {
            "id": str(record.id),
            "user_id": record.user_id,
            "organization_id": record.organization_id,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "status": record.status,
            "current_agent": record.current_agent,
            "progress_percentage": record.progress_percentage,
            "estimated_completion": record.estimated_completion.isoformat() if record.estimated_completion else None,
            "goal": record.goal,
            "content_request": record.content_request,
            "qa_execution_data": record.qa_execution_data,
            "name": record.name,
            "strategy": record.strategy,
            "content": record.content,
            "media_plan": record.media_plan,
            "performance": record.performance,
            "report": record.report,
            "error": record.error,
            "pending_approval": record.pending_approval,
            "approvals": record.approvals,
            "human_in_the_loop": record.human_in_the_loop,
            "auto_approve": record.auto_approve,
        }

    def _record_from_snapshot(self, data: dict[str, Any]) -> CampaignRecord:
        return CampaignRecord(
            id=UUID(str(data["id"])),
            user_id=str(data.get("user_id") or ""),
            organization_id=str(data.get("organization_id") or ""),
            created_at=self._parse_optional_dt(data.get("created_at")) or datetime.now(UTC),
            updated_at=self._parse_optional_dt(data.get("updated_at")) or datetime.now(UTC),
            status=str(data.get("status") or "queued"),
            current_agent=data.get("current_agent"),
            progress_percentage=int(data.get("progress_percentage", 0)),
            estimated_completion=self._parse_optional_dt(data.get("estimated_completion")),
            goal=data.get("goal") if isinstance(data.get("goal"), dict) else {},
            content_request=(str(data.get("content_request")).strip() if data.get("content_request") else None),
            qa_execution_data=data.get("qa_execution_data") if isinstance(data.get("qa_execution_data"), dict) else None,
            name=data.get("name"),
            strategy=data.get("strategy") if isinstance(data.get("strategy"), dict) else None,
            content=data.get("content") if isinstance(data.get("content"), dict) else None,
            media_plan=data.get("media_plan") if isinstance(data.get("media_plan"), dict) else None,
            performance=data.get("performance") if isinstance(data.get("performance"), dict) else None,
            report=data.get("report") if isinstance(data.get("report"), dict) else None,
            error=data.get("error") if isinstance(data.get("error"), str) else None,
            pending_approval=data.get("pending_approval") if isinstance(data.get("pending_approval"), dict) else None,
            approvals=data.get("approvals") if isinstance(data.get("approvals"), dict) else {"strategy": False, "media_plan": False},
            human_in_the_loop=bool(data.get("human_in_the_loop", True)),
            auto_approve=bool(data.get("auto_approve", False)),
        )

    def _save_local_snapshot(self) -> None:
        try:
            payload = {
                "campaigns": [self._record_to_snapshot(record) for record in self._campaigns.values()],
            }
            self._snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
        except Exception as exc:
            logger.debug("campaign_snapshot_save_failed", error=str(exc), path=str(self._snapshot_path))

    def _load_local_snapshot(self) -> None:
        try:
            if not self._snapshot_path.exists():
                return
            raw = json.loads(self._snapshot_path.read_text(encoding="utf-8"))
            rows = raw.get("campaigns", []) if isinstance(raw, dict) else []
            if not isinstance(rows, list):
                return
            for row in rows:
                if isinstance(row, dict):
                    record = self._record_from_snapshot(row)
                    self._campaigns[record.id] = record
        except Exception as exc:
            logger.debug("campaign_snapshot_load_failed", error=str(exc), path=str(self._snapshot_path))

    def _error_text(self, exc: Exception) -> str:
        return str(exc).lower()

    def _is_missing_admin_config(self, exc: Exception) -> bool:
        message = self._error_text(exc)
        return "service_role_key is required" in message

    def _is_connectivity_error(self, exc: Exception) -> bool:
        message = self._error_text(exc)
        connectivity_markers = (
            "getaddrinfo failed",
            "name or service not known",
            "temporary failure in name resolution",
            "connection refused",
            "connecterror",
            "timed out",
            "timeout",
            "[errno 11001]",
        )
        return any(marker in message for marker in connectivity_markers)

    def _is_org_fk_violation(self, exc: Exception) -> bool:
        message = self._error_text(exc)
        return "organization_id" in message and ("foreign key" in message or "violates" in message)

    def _is_user_fk_violation(self, exc: Exception) -> bool:
        message = self._error_text(exc)
        return "user_id" in message and ("foreign key" in message or "violates" in message)

    def _is_missing_column_error(self, exc: Exception) -> bool:
        message = self._error_text(exc)
        return "does not exist" in message or "could not find" in message

    def _ensure_legacy_organization_row(self, organization_id: str) -> bool:
        """Backfill legacy `organizations` row when auth uses `app_organizations` IDs."""
        try:
            existing = self.admin.table("organizations").select("id").eq("id", organization_id).limit(1).execute()
            if existing.data:
                return True

            app_org = self.admin.table("app_organizations").select("id,name").eq("id", organization_id).limit(1).execute()
            if not app_org.data:
                return False

            name = str(app_org.data[0].get("name") or "Organization")
            self.admin.table("organizations").insert({"id": organization_id, "name": name}).execute()
            return True
        except Exception as exc:
            logger.debug("campaign_org_mirror_failed", organization_id=organization_id, error=str(exc))
            return False

    @property
    def admin(self):
        if self._admin is None:
            self._admin = get_supabase_admin_client()
        return self._admin

    def _runtime_from_record(self, record: CampaignRecord) -> dict[str, Any]:
        return {
            "status": record.status,
            "current_agent": record.current_agent,
            "progress_percentage": record.progress_percentage,
            "estimated_completion": record.estimated_completion.isoformat() if record.estimated_completion else None,
            "goal_input": record.goal,
            "content_request": record.content_request,
            "qa_execution_data": record.qa_execution_data,
            "strategy": record.strategy,
            "content": record.content,
            "media_plan": record.media_plan,
            "performance": record.performance,
            "report": record.report,
            "error": record.error,
            "pending_approval": record.pending_approval,
            "approvals": record.approvals,
            "human_in_the_loop": record.human_in_the_loop,
            "auto_approve": record.auto_approve,
        }

    def _db_has_column(self, column: str) -> bool:
        cached = self._campaign_columns.get(column)
        if cached is not None:
            return cached

        try:
            self.admin.table("campaigns").select(column).limit(1).execute()
            self._campaign_columns[column] = True
            return True
        except Exception as exc:
            if self._is_missing_column_error(exc):
                self._campaign_columns[column] = False
                return False
            raise

    def _parse_optional_dt(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value.astimezone(UTC)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)

    def _db_status(self, runtime_status: str) -> str:
        if runtime_status == "completed":
            return "completed"
        if runtime_status == "failed":
            return "failed"
        if runtime_status == "queued":
            return "draft"
        return "active"

    def _record_from_db_row(self, row: dict[str, Any]) -> CampaignRecord:
        runtime = {}
        strategy_json = row.get("strategy_json")
        if isinstance(strategy_json, dict):
            runtime = strategy_json.get("runtime") if isinstance(strategy_json.get("runtime"), dict) else {}

        goal_input = runtime.get("goal_input") if isinstance(runtime.get("goal_input"), dict) else {}
        content_request = str(runtime.get("content_request") or "").strip() or None
        qa_execution_data = runtime.get("qa_execution_data") if isinstance(runtime.get("qa_execution_data"), dict) else None
        if not goal_input:
            row_goal = row.get("goal")
            if isinstance(row_goal, dict):
                goal_input = row_goal
            elif isinstance(row_goal, str) and row_goal.strip():
                goal_input = {
                    "goal": row_goal.strip(),
                    "budget": float(row.get("budget") or 0),
                    "timeline_days": 30,
                    "industry": "General",
                    "product_description": "Campaign",
                }

        record_name = str(row.get("name") or "").strip() or str(goal_input.get("campaign_name") or "").strip()
        if not record_name:
            record_name = str(goal_input.get("goal") or "Autonomous Campaign")[:120]

        record_org = str(row.get("organization_id") or "").strip() or str(goal_input.get("_organization_id") or "").strip()

        created = self._parse_optional_dt(row.get("created_at")) or datetime.now(UTC)
        updated = self._parse_optional_dt(row.get("updated_at")) or created
        runtime_status = str(runtime.get("status") or row.get("status") or "queued")
        estimated_completion = self._parse_optional_dt(runtime.get("estimated_completion"))

        return CampaignRecord(
            id=UUID(str(row["id"])),
            user_id=str(row.get("user_id") or ""),
            organization_id=record_org,
            created_at=created,
            updated_at=updated,
            status=runtime_status,
            current_agent=runtime.get("current_agent"),
            progress_percentage=int(runtime.get("progress_percentage", _progress_from_status(runtime_status))),
            estimated_completion=estimated_completion,
            name=record_name,
            goal=goal_input,
            content_request=content_request,
            qa_execution_data=qa_execution_data,
            strategy=runtime.get("strategy") if isinstance(runtime.get("strategy"), dict) else None,
            content=runtime.get("content") if isinstance(runtime.get("content"), dict) else None,
            media_plan=runtime.get("media_plan") if isinstance(runtime.get("media_plan"), dict) else None,
            performance=runtime.get("performance") if isinstance(runtime.get("performance"), dict) else None,
            report=runtime.get("report") if isinstance(runtime.get("report"), dict) else None,
            error=str(runtime.get("error")) if runtime.get("error") else None,
            pending_approval=runtime.get("pending_approval") if isinstance(runtime.get("pending_approval"), dict) else None,
            approvals=runtime.get("approvals") if isinstance(runtime.get("approvals"), dict) else {"strategy": False, "media_plan": False},
            human_in_the_loop=bool(runtime.get("human_in_the_loop", True)),
            auto_approve=bool(runtime.get("auto_approve", False)),
        )

    def _create_name_from_goal(self, goal: dict[str, Any]) -> str:
        raw = str(goal.get("goal") or "Autonomous Campaign")
        return raw[:120]

    def _to_db_insert(self, record: CampaignRecord) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": str(record.id),
            "user_id": record.user_id,
            "status": self._db_status(record.status),
            "budget": int(round(float(record.goal.get("budget", 0) or 0))),
        }

        if self._db_has_column("organization_id"):
            payload["organization_id"] = record.organization_id
        if self._db_has_column("name"):
            payload["name"] = str(record.name or self._create_name_from_goal(record.goal))
        if self._db_has_column("description"):
            payload["description"] = str(record.goal.get("product_description") or "")
        if self._db_has_column("goals"):
            payload["goals"] = [str(record.goal.get("goal") or "Campaign objective")]
        if self._db_has_column("target_audience"):
            payload["target_audience"] = {
                "industry": record.goal.get("industry"),
                "segment": record.goal.get("target_audience"),
            }
        if self._db_has_column("timeline"):
            payload["timeline"] = {
                "startDate": datetime.now(UTC).date().isoformat(),
                "endDate": (datetime.now(UTC) + timedelta(days=int(record.goal.get("timeline_days", 30)))).date().isoformat(),
                "phases": [{"name": "execution", "days": int(record.goal.get("timeline_days", 30))}],
            }
        if self._db_has_column("strategy_json"):
            payload["strategy_json"] = {
                "summary": "",
                "targeting": {},
                "messaging": {},
                "budget_allocation": {},
                "runtime": self._runtime_from_record(record),
            }

        # Legacy schemas can have a NOT NULL goal column alongside strategy_json.
        if self._db_has_column("goal"):
            payload["goal"] = str(record.goal.get("goal") or "Campaign objective")

        return payload

    def _persist_update_payload(self, record: CampaignRecord) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self._db_status(record.status),
            "budget": int(round(float(record.goal.get("budget", 0) or 0))),
        }
        if self._db_has_column("strategy_json"):
            payload["strategy_json"] = {
                "summary": "",
                "targeting": {},
                "messaging": {},
                "budget_allocation": {},
                "runtime": self._runtime_from_record(record),
            }
        if self._db_has_column("goals"):
            payload["goals"] = [str(record.goal.get("goal") or "Campaign objective")]

        # Keep legacy goal column populated in mixed schemas.
        if self._db_has_column("goal"):
            payload["goal"] = str(record.goal.get("goal") or "Campaign objective")
        return payload

    async def create_campaign(self, user_id: str, organization_id: str, payload: dict[str, Any]) -> CampaignRecord:
        now = datetime.now(UTC)
        campaign_id = uuid4()
        campaign_name = str(payload.get("campaign_name") or "").strip() or self._create_name_from_goal(payload["goal"])
        record = CampaignRecord(
            id=campaign_id,
            user_id=user_id,
            organization_id=organization_id,
            created_at=now,
            updated_at=now,
            status="queued",
            current_agent="supervisor",
            progress_percentage=5,
            estimated_completion=now + timedelta(minutes=5),
            name=campaign_name,
            goal=payload["goal"],
            content_request=(str(payload.get("content_request") or "").strip() or None),
            qa_execution_data=payload.get("qa_execution_data") if isinstance(payload.get("qa_execution_data"), dict) else None,
            human_in_the_loop=payload.get("human_in_the_loop", True),
            auto_approve=payload.get("auto_approve", False),
        )

        if self._db_available:
            try:
                self.admin.table("campaigns").insert(self._to_db_insert(record)).execute()
            except Exception as exc:
                if self._is_org_fk_violation(exc) and self._ensure_legacy_organization_row(organization_id):
                    self.admin.table("campaigns").insert(self._to_db_insert(record)).execute()
                elif self._is_user_fk_violation(exc):
                    logger.error("campaign_db_user_fk_mismatch", user_id=user_id, error=str(exc))
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Campaign persistence blocked by legacy user foreign key. Run migration 004_campaigns_schema_reconcile.sql.",
                    ) from exc
                elif self._is_missing_admin_config(exc) or self._is_connectivity_error(exc):
                    # Keep test/local no-Supabase workflows working.
                    self._db_available = False
                    logger.warning("campaign_db_create_inmemory_only", error=str(exc))
                else:
                    logger.error("campaign_db_create_failed", organization_id=organization_id, error=str(exc))
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Campaign persistence failed. Please retry.",
                    ) from exc

        async with self._lock:
            self._campaigns[campaign_id] = record
            self._save_local_snapshot()
        await self.publish_event(
            campaign_id,
            {"event": "campaign_created", "campaign_id": str(campaign_id), "organization_id": organization_id},
        )
        return record

    async def get_campaign(self, campaign_id: UUID) -> CampaignRecord:
        async with self._lock:
            record = self._campaigns.get(campaign_id)

        if record:
            return record

        if self._db_available:
            try:
                query = self.admin.table("campaigns").select("*").eq("id", str(campaign_id)).limit(1).execute()
                if query.data:
                    db_record = self._record_from_db_row(query.data[0])
                    async with self._lock:
                        self._campaigns[campaign_id] = db_record
                    return db_record
            except Exception as exc:
                if self._is_missing_admin_config(exc) or self._is_connectivity_error(exc):
                    self._db_available = False
                    logger.warning("campaign_db_get_inmemory_only", campaign_id=str(campaign_id), error=str(exc))
                else:
                    logger.error("campaign_db_get_failed", campaign_id=str(campaign_id), error=str(exc))
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Campaign store unavailable. Please retry.",
                    ) from exc

        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
        return record

    async def list_campaigns(self, user_id: str) -> list[CampaignRecord]:
        if self._db_available:
            try:
                query = self.admin.table("campaigns").select("*").eq("user_id", user_id).execute()
                records = [self._record_from_db_row(row) for row in (query.data or [])]
                async with self._lock:
                    for item in records:
                        self._campaigns[item.id] = item
                return records
            except Exception as exc:
                self._db_available = False
                logger.warning("campaign_db_list_fallback", user_id=user_id, error=str(exc))

        async with self._lock:
            return [c for c in self._campaigns.values() if c.user_id == user_id]

    async def list_campaigns_by_org(
        self,
        org_id: str,
        limit: int = 50,
        offset: int = 0,
        user_id: str | None = None,
    ) -> list[CampaignRecord]:
        """List campaigns for an organization with pagination."""
        if self._db_available:
            try:
                builder = self.admin.table("campaigns").select("*").order("updated_at", desc=True).range(offset, offset + limit - 1)
                if self._db_has_column("organization_id"):
                    builder = builder.eq("organization_id", org_id)
                elif user_id and self._db_has_column("user_id"):
                    builder = builder.eq("user_id", user_id)

                query = builder.execute()
                records = [self._record_from_db_row(row) for row in (query.data or [])]
                async with self._lock:
                    for item in records:
                        self._campaigns[item.id] = item
                return records
            except Exception as exc:
                logger.debug("campaign_db_list_org_direct_failed", org_id=org_id, error=str(exc))

        async with self._lock:
            all_campaigns = [c for c in self._campaigns.values() if c.organization_id == org_id]
            return sorted(all_campaigns, key=lambda c: c.updated_at, reverse=True)[offset : offset + limit]

    async def count_campaigns(self, org_id: str, user_id: str | None = None) -> int:
        """Count total campaigns for an organization."""
        if self._db_available:
            try:
                builder = self.admin.table("campaigns").select("id", count="exact")
                if self._db_has_column("organization_id"):
                    builder = builder.eq("organization_id", org_id)
                elif user_id and self._db_has_column("user_id"):
                    builder = builder.eq("user_id", user_id)
                query = builder.execute()
                return query.count or 0
            except Exception as exc:
                self._db_available = False
                logger.warning("campaign_db_count_org_fallback", org_id=org_id, error=str(exc))

        async with self._lock:
            return len([c for c in self._campaigns.values() if c.organization_id == org_id])

    async def update_campaign(self, campaign_id: UUID, **kwargs: Any) -> CampaignRecord:
        async with self._lock:
            record = self._campaigns.get(campaign_id)
            if not record:
                record = None

        if record is None:
            record = await self.get_campaign(campaign_id)

        next_record = copy.deepcopy(record)
        for key, value in kwargs.items():
            setattr(next_record, key, value)
        next_record.updated_at = datetime.now(UTC)

        if self._db_available:
            try:
                self.admin.table("campaigns").update(self._persist_update_payload(next_record)).eq("id", str(campaign_id)).execute()
            except Exception as exc:
                self._db_available = False
                logger.warning("campaign_db_update_fallback", campaign_id=str(campaign_id), error=str(exc))

        async with self._lock:
            self._campaigns[campaign_id] = next_record
            self._save_local_snapshot()
            return next_record

    async def delete_campaign(self, campaign_id: UUID) -> None:
        if self._db_available:
            try:
                self.admin.table("campaigns").delete().eq("id", str(campaign_id)).execute()
            except Exception as exc:
                logger.warning("campaign_db_delete_fallback", campaign_id=str(campaign_id), error=str(exc))

        async with self._lock:
            self._campaigns.pop(campaign_id, None)
            self._subscribers.pop(campaign_id, None)
            self._save_local_snapshot()

    async def subscribe(self, campaign_id: UUID) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._lock:
            self._subscribers.setdefault(campaign_id, []).append(q)
        return q

    async def unsubscribe(self, campaign_id: UUID, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            current = self._subscribers.get(campaign_id, [])
            self._subscribers[campaign_id] = [q for q in current if q is not queue]

    async def publish_event(self, campaign_id: UUID, payload: dict[str, Any]) -> None:
        async with self._lock:
            subscribers = list(self._subscribers.get(campaign_id, []))
        for q in subscribers:
            await q.put(payload)


store = CampaignStore()


def _progress_from_status(status: str) -> int:
    mapping = {
        "queued": 5,
        "running": 20,
        "strategy_ready": 35,
        "awaiting_strategy_approval": 45,
        "running_parallel_generation": 55,
        "content_ready": 65,
        "media_plan_ready": 70,
        "awaiting_budget_approval": 75,
        "performance_ready": 85,
        "completed": 100,
        "failed": 100,
    }
    return mapping.get(status, 20)


def _future_eta(progress: int) -> datetime | None:
    if progress >= 100:
        return None
    minutes = max(1, int((100 - progress) / 8))
    return datetime.now(UTC) + timedelta(minutes=minutes)


def _default_execution_data(goal: dict[str, Any]) -> dict[str, Any]:
    budget = float(goal.get("budget", 0) or 0)
    timeline_days = max(1, int(goal.get("timeline_days", 30) or 30))

    if budget <= 0:
        return {
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "spend": 0.0,
            "revenue": 0.0,
            "unique_reach": 0,
            "objective": "conversion",
            "campaign_duration_days": timeline_days,
            "target_metrics": {},
            "time_series_data": [],
        }

    spend = min(max(budget * 0.24, 1000.0), budget)
    impressions = int(max(5000, spend * 9))
    clicks = int(max(50, impressions * 0.027))
    conversions = int(max(1, clicks * 0.042))
    revenue = float(spend * 2.8)
    unique_reach = int(max(1000, impressions * 0.45))

    return {
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "spend": round(spend, 2),
        "revenue": round(revenue, 2),
        "unique_reach": unique_reach,
        "objective": "conversion",
        "campaign_duration_days": timeline_days,
        "target_metrics": {},
        "time_series_data": [],
    }


async def _workflow_deps(campaign_id: UUID) -> dict[str, Any]:
    async def planner(state: dict[str, Any]) -> dict[str, Any]:
        started = monotonic()
        await websocket_manager.broadcast(
            campaign_id,
            WebSocketEventType.AGENT_STARTED,
            {
                "agent_name": "strategic_planner",
                "input_summary": "Generating campaign strategy from goal",
            },
        )

        goal = state.get("campaign_goal", {})
        budget = float(goal.get("budget", 0))
        result = {
            "campaign_strategy": {
                "objectives": [goal.get("goal", "Grow campaign outcomes")],
                "target_audiences": [
                    {
                        "name": "Growth Manager",
                        "segment": "B2B",
                        "demographics": ["Age 28-45"],
                        "pain_points": ["High CAC"],
                        "motivations": ["Pipeline growth"],
                    },
                    {
                        "name": "RevOps Lead",
                        "segment": "B2B",
                        "demographics": ["North America"],
                        "pain_points": ["Fragmented data"],
                        "motivations": ["Predictable ROI"],
                    },
                ],
                "key_messages": ["Automate and optimize campaign execution"],
                "recommended_channels": [
                    {
                        "channel": "google_ads",
                        "budget_percentage": 50,
                        "rationale": "High-intent demand capture",
                        "execution_notes": ["Scale winning keywords"],
                    },
                    {
                        "channel": "meta_ads",
                        "budget_percentage": 30,
                        "rationale": "Audience reach and retargeting",
                        "execution_notes": ["Refresh creative weekly"],
                    },
                    {
                        "channel": "linkedin_ads",
                        "budget_percentage": 20,
                        "rationale": "B2B precision targeting",
                        "execution_notes": ["Job-title segments"],
                    },
                ],
                "timeline": [
                    {
                        "day": 1,
                        "title": "Launch",
                        "description": "Deploy baseline campaigns",
                        "success_criteria": "Tracking QA completed",
                    }
                ],
                "budget_allocation": {
                    "google_ads": round(budget * 0.5, 2),
                    "meta_ads": round(budget * 0.3, 2),
                    "linkedin_ads": round(budget * 0.2, 2),
                },
                "competitive_differentiation": ["Faster optimization loops"],
                "confidence_score": 0.82,
            }
        }
        await websocket_manager.broadcast(
            campaign_id,
            WebSocketEventType.AGENT_COMPLETED,
            {
                "agent_name": "strategic_planner",
                "output_summary": "Strategy generated",
                "latency": round((monotonic() - started) * 1000, 2),
            },
        )
        return result

    async def content_creator(_state: dict[str, Any]) -> dict[str, Any]:
        started = monotonic()
        await websocket_manager.broadcast(
            campaign_id,
            WebSocketEventType.AGENT_STARTED,
            {
                "agent_name": "content_creator",
                "input_summary": "Generating content assets",
            },
        )

        result = {
            "content_package": {
                "assets": [
                    {
                        "asset_id": "ad-1",
                        "asset_type": "ad_copy",
                        "platform": "google_ads",
                        "persona_name": "Growth Manager",
                        "title": "Scale Qualified Pipeline",
                        "body": "Launch smarter campaigns with autonomous optimization.",
                        "cta": "Book Demo",
                        "variant": "A",
                        "utm_parameters": {
                            "source": "google",
                            "medium": "cpc",
                            "campaign": "acm_launch",
                            "content": "ad-1",
                            "term": None,
                        },
                        "ab_test": {
                            "variant_a": "ROI angle",
                            "variant_b": "Speed angle",
                            "hypothesis": "ROI angle improves CTR",
                        },
                        "metadata": {},
                    }
                ]
            },
            "content_valid": True,
            "content_quality_issues": [],
        }
        await websocket_manager.broadcast(
            campaign_id,
            WebSocketEventType.AGENT_COMPLETED,
            {
                "agent_name": "content_creator",
                "output_summary": "Content package ready",
                "latency": round((monotonic() - started) * 1000, 2),
            },
        )
        return result

    async def media_buyer(state: dict[str, Any]) -> dict[str, Any]:
        started = monotonic()
        await websocket_manager.broadcast(
            campaign_id,
            WebSocketEventType.AGENT_STARTED,
            {
                "agent_name": "media_buyer",
                "input_summary": "Allocating channel budget and media plan",
            },
        )

        total_budget = float(state.get("total_budget", 0))
        result = {
            "media_plan": {
                "channels": [
                    {
                        "channel": "google_ads",
                        "budget": round(total_budget * 0.5, 2),
                        "budget_percentage": 50,
                        "bid_strategy": "target CPA",
                        "targeting": {
                            "demographics": ["Age 28-45"],
                            "interests": ["Growth marketing"],
                            "behaviors": ["B2B buyers"],
                            "lookalike_audiences": ["MQL lookalike"],
                        },
                        "projected_reach": 300000,
                        "projected_impressions": 600000,
                        "projected_clicks": 15000,
                        "projected_conversions": 700,
                        "rationale": "Best intent capture",
                    }
                ],
                "total_budget": total_budget,
                "daily_budget": round(total_budget / 30, 2) if total_budget else 0.0,
                "bid_strategy": "target CPA",
                "targeting": {
                    "demographics": ["Age 28-45"],
                    "interests": ["Growth marketing"],
                    "behaviors": ["B2B buyers"],
                    "lookalike_audiences": ["MQL lookalike"],
                },
                "flight_dates": {
                    "start_date": datetime.now(UTC).date().isoformat(),
                    "end_date": (datetime.now(UTC).date() + timedelta(days=30)).isoformat(),
                    "dayparting_recommendations": ["09:00-18:00 local"],
                },
            },
            "media_plan_valid": True,
            "media_plan_issues": [],
        }
        await websocket_manager.broadcast(
            campaign_id,
            WebSocketEventType.AGENT_COMPLETED,
            {
                "agent_name": "media_buyer",
                "output_summary": "Media plan generated",
                "latency": round((monotonic() - started) * 1000, 2),
            },
        )
        return result

    async def performance_analyst(_state: dict[str, Any]) -> dict[str, Any]:
        started = monotonic()
        await websocket_manager.broadcast(
            campaign_id,
            WebSocketEventType.AGENT_STARTED,
            {
                "agent_name": "performance_analyst",
                "input_summary": "Analyzing campaign performance",
            },
        )

        result = {
            "performance_report": {
                "metrics": {
                    "ctr": 0.024,
                    "cpc": 2.1,
                    "cpa": 58,
                    "roas": 3.1,
                    "conversion_rate": 0.04,
                    "frequency": 2.9,
                },
                "anomalies": [],
                "recommendations": [
                    {
                        "category": "budget_reallocation",
                        "action": "Shift 10% to highest ROAS channels",
                        "rationale": "Improve blended efficiency",
                        "expected_impact": "Lower CPA",
                        "priority": "high",
                    }
                ],
                "optimization_score": 0.8,
                "projected_end_of_campaign": {
                    "projected_revenue": 280000,
                    "projected_spend": 96000,
                    "projected_roas": 2.92,
                },
                "underperforming_channels": [],
                "underperforming_assets": [],
            }
        }
        await websocket_manager.broadcast(
            campaign_id,
            WebSocketEventType.AGENT_COMPLETED,
            {
                "agent_name": "performance_analyst",
                "output_summary": "Performance report generated",
                "latency": round((monotonic() - started) * 1000, 2),
            },
        )
        await websocket_manager.broadcast(
            campaign_id,
            WebSocketEventType.OPTIMIZATION_ALERT,
            {
                "severity": "medium",
                "message": "Optimization opportunity detected in channel mix",
                "recommendation": "Shift 10% budget toward top ROAS channels",
            },
        )
        return result

    async def reporter(_state: dict[str, Any]) -> dict[str, Any]:
        started = monotonic()
        await websocket_manager.broadcast(
            campaign_id,
            WebSocketEventType.AGENT_STARTED,
            {
                "agent_name": "campaign_reporter",
                "input_summary": "Compiling final campaign report",
            },
        )

        result = {
            "final_report": {
                "executive_summary": "Campaign delivered above-target return with stable efficiency.",
                "detailed_sections": [],
                "charts_data": {"spend_allocation_pie": []},
                "recommendations": ["Scale best-performing channel mix"],
                "next_steps": ["Approve next quarter strategy"],
            },
            "report_exports": {
                "json": {
                    "executive_summary": "Campaign delivered above-target return with stable efficiency."
                },
                "markdown": "# Campaign Final Report\n\n## Executive Summary\nCampaign delivered above-target return with stable efficiency.",
                "pdf": {"available": False, "bytes": None, "error": "reportlab not installed"},
            },
        }
        await websocket_manager.broadcast(
            campaign_id,
            WebSocketEventType.AGENT_COMPLETED,
            {
                "agent_name": "campaign_reporter",
                "output_summary": "Final report created",
                "latency": round((monotonic() - started) * 1000, 2),
            },
        )
        return result

    return {
        "planner": planner,
        "content_creator": content_creator,
        "media_buyer": media_buyer,
        "performance_analyst": performance_analyst,
        "reporter": reporter,
    }


def _load_orchestrator():
    """Load orchestrator from agents package."""
    repo_root = Path(__file__).resolve().parents[5]
    agents_pkg = repo_root / "backend" / "packages" / "agents"
    
    # Verify the path exists
    if not agents_pkg.exists():
        raise RuntimeError(f"Agents package not found at {agents_pkg}")
    
    # Add agents directory to sys.path so we can import src package
    if str(agents_pkg) not in sys.path:
        sys.path.insert(0, str(agents_pkg))
    
    # Debug logging
    logger.info(
        "loading_orchestrator",
        agents_pkg=str(agents_pkg),
        agents_pkg_exists=agents_pkg.exists(),
        src_exists=(agents_pkg / "src").exists(),
        orchestrator_exists=(agents_pkg / "src" / "orchestrator.py").exists(),
    )
    
    # Now import from src package
    try:
        from src.orchestrator import run_campaign_workflow_once  # type: ignore
        logger.info(
            "orchestrator_loaded_successfully",
            orchestrator_path="src.orchestrator",
        )
        return run_campaign_workflow_once
    except ImportError as e:
        logger.exception("orchestrator_import_failed", error=str(e))
        raise


async def execute_workflow(campaign_id: UUID, *, manual_report_trigger: bool = False) -> None:
    record = await store.get_campaign(campaign_id)

    await store.update_campaign(
        campaign_id,
        status="running",
        current_agent="supervisor",
        progress_percentage=20,
        estimated_completion=_future_eta(20),
        error=None,
    )
    await store.publish_event(campaign_id, {"event": "workflow_started", "campaign_id": str(campaign_id)})
    await websocket_manager.broadcast(
        campaign_id,
        WebSocketEventType.AGENT_STARTED,
        {
            "agent_name": "supervisor",
            "input_summary": "Campaign workflow initiated",
        },
    )

    try:
        run_campaign_workflow_once = _load_orchestrator()
        deps = await _workflow_deps(campaign_id)

        async def _run_once() -> dict[str, Any]:
            initial_state = {
            "messages": [],
            "current_agent": record.current_agent,
            "strategy": record.strategy,
            "content": record.content,
            "media_plan": record.media_plan,
            "performance": record.performance,
            "report": record.report,
            "status": record.status,
            "error": record.error,
            "campaign_goal": record.goal,
            "content_request": record.content_request,
            "brand_guidelines": {
                "tone": "clear",
                "voice": "expert",
                "prohibited_words": [],
                "brand_colors": ["#123456"],
            },
            "total_budget": record.goal.get("budget", 0),
            "campaign_execution_data": record.qa_execution_data or _default_execution_data(record.goal),
            "agent_logs": [],
            "retry_counts": {},
            "last_failed_agent": None,
            "planner_feedback": None,
            "strategy_confidence_threshold": 0.7,
            "monitor_interval_hours": 6,
            "next_monitor_at": None,
            "monitor_cycles": 0,
            "max_monitor_cycles": 1,
            "strategy_approved": record.approvals.get("strategy", False),
            "budget_approved": record.approvals.get("media_plan", False),
            "human_in_the_loop": record.human_in_the_loop,
            "auto_approve": record.auto_approve,
            "pending_approval": record.pending_approval,
            "manual_report_trigger": manual_report_trigger,
            "campaign_complete": False,
            }
            return await run_campaign_workflow_once(initial_state, deps=deps)

        try:
            final_state = await _run_once()
        except Exception as exc:
            logger.warning("workflow_retry", campaign_id=str(campaign_id), error=str(exc))
            await asyncio.sleep(1)
            final_state = await _run_once()

        status_value = final_state.get("status", "running")
        progress = _progress_from_status(status_value)
        await store.update_campaign(
            campaign_id,
            status=status_value,
            current_agent=final_state.get("current_agent"),
            strategy=final_state.get("strategy"),
            content=final_state.get("content"),
            media_plan=final_state.get("media_plan"),
            performance=final_state.get("performance"),
            report=final_state.get("report"),
            error=final_state.get("error"),
            pending_approval=final_state.get("pending_approval"),
            progress_percentage=progress,
            estimated_completion=_future_eta(progress),
        )

        await store.publish_event(
            campaign_id,
            {
                "event": "workflow_updated",
                "campaign_id": str(campaign_id),
                "status": status_value,
                "current_agent": final_state.get("current_agent"),
                "progress_percentage": progress,
                "pending_approval": final_state.get("pending_approval"),
            },
        )

        await websocket_manager.broadcast(
            campaign_id,
            WebSocketEventType.AGENT_COMPLETED,
            {
                "agent_name": "supervisor",
                "output_summary": f"Workflow status: {status_value}",
                "latency": 0,
            },
        )

        pending_approval = final_state.get("pending_approval")
        if pending_approval:
            await websocket_manager.broadcast(
                campaign_id,
                WebSocketEventType.HUMAN_APPROVAL_REQUIRED,
                {
                    "step": pending_approval.get("type", "unknown"),
                    "payload": pending_approval,
                    "timeout": 600,
                },
            )

        if status_value == "completed" and final_state.get("report"):
            await websocket_manager.broadcast(
                campaign_id,
                WebSocketEventType.CAMPAIGN_COMPLETED,
                {
                    "campaign_id": str(campaign_id),
                    "report_url": f"/api/v1/campaigns/{campaign_id}/report?format=json",
                },
            )

        if final_state.get("error"):
            retry_counts = final_state.get("retry_counts") or {}
            current_agent = final_state.get("current_agent") or "supervisor"
            retry_count = int(retry_counts.get(current_agent, 0))
            await websocket_manager.broadcast(
                campaign_id,
                WebSocketEventType.ERROR,
                {
                    "agent_name": current_agent,
                    "error_message": str(final_state.get("error")),
                    "retry_count": retry_count,
                },
            )
    except Exception as exc:
        logger.exception("workflow_execution_failed", campaign_id=str(campaign_id), error=str(exc))
        await store.update_campaign(
            campaign_id,
            status="failed",
            current_agent="supervisor",
            error=str(exc),
            progress_percentage=100,
            estimated_completion=None,
        )
        await store.publish_event(
            campaign_id,
            {
                "event": "workflow_failed",
                "campaign_id": str(campaign_id),
                "error": str(exc),
            },
        )
        await websocket_manager.broadcast(
            campaign_id,
            WebSocketEventType.ERROR,
            {
                "agent_name": "supervisor",
                "error_message": str(exc),
                "retry_count": 0,
            },
        )


def report_as_format(report: dict[str, Any], fmt: str) -> dict[str, Any]:
    if fmt == "json":
        exports = report.get("report_exports")
        if isinstance(exports, dict) and isinstance(exports.get("json"), dict):
            return {"format": "json", "content": exports.get("json")}
        return {"format": "json", "content": report}

    if fmt == "markdown":
        exports = report.get("report_exports")
        if isinstance(exports, dict) and isinstance(exports.get("markdown"), str):
            markdown = str(exports.get("markdown"))
        else:
            summary = report.get("executive_summary", "")
            markdown = f"# Campaign Final Report\n\n## Executive Summary\n{summary}"
        return {"format": "markdown", "content": markdown}

    if fmt == "pdf":
        exports = report.get("report_exports")
        if isinstance(exports, dict):
            pdf_export = exports.get("pdf")
            if isinstance(pdf_export, dict):
                raw_pdf = pdf_export.get("bytes")
                if isinstance(raw_pdf, str) and raw_pdf:
                    return {"format": "pdf", "content": raw_pdf, "encoding": "base64"}
        encoded = base64.b64encode(b"%PDF-1.4\n% ACM placeholder\n").decode("utf-8")
        return {"format": "pdf", "content": encoded, "encoding": "base64"}

    raise HTTPException(status_code=400, detail="Unsupported format")
