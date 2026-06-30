"""Campaign API models for the autonomous workflow backend."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CampaignRuntimeStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_STRATEGY_APPROVAL = "awaiting_strategy_approval"
    AWAITING_BUDGET_APPROVAL = "awaiting_budget_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class CampaignGoalInput(BaseModel):
    goal: str = Field(..., min_length=5, max_length=600)
    budget: float = Field(..., ge=0)
    timeline_days: int = Field(..., ge=1, le=3650)
    target_audience: str | None = Field(default=None, min_length=2, max_length=300)
    industry: str = Field(..., min_length=2, max_length=120)
    product_description: str = Field(..., min_length=10, max_length=4000)


class CampaignCreateRequest(BaseModel):
    campaign_name: str | None = Field(default=None, min_length=2, max_length=120)
    goal: CampaignGoalInput
    content_request: str | None = Field(default=None, min_length=5, max_length=2000)
    human_in_the_loop: bool = True
    auto_approve: bool = False


class CampaignCreateResponse(BaseModel):
    campaign_id: UUID
    status: CampaignRuntimeStatus


class CampaignSummary(BaseModel):
    campaign_id: UUID
    name: str | None = None
    status: str
    budget_total: float | None = None
    roi: float | None = None
    current_agent: str | None = None
    progress_percentage: int = Field(default=0, ge=0, le=100)
    estimated_completion: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CampaignListResponse(BaseModel):
    campaigns: list[CampaignSummary]
    total: int


class CampaignStateResponse(BaseModel):
    campaign_id: UUID
    status: str
    current_agent: str | None = None
    progress_percentage: int = Field(default=0, ge=0, le=100)
    estimated_completion: datetime | None = None
    strategy: dict[str, Any] | None = None
    content: dict[str, Any] | None = None
    media_plan: dict[str, Any] | None = None
    performance: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    pending_approval: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class CampaignStatusResponse(BaseModel):
    campaign_id: UUID
    status: str
    current_agent: str | None = None
    progress_percentage: int = Field(default=0, ge=0, le=100)
    estimated_completion: datetime | None = None
    error: str | None = None


class CampaignApprovalRequest(BaseModel):
    approval_type: Literal["strategy", "media_plan"]
    approved: bool
    feedback: str = Field(default="", max_length=2000)


class CampaignApprovalResponse(BaseModel):
    campaign_id: UUID
    status: str
    message: str


class CampaignContentResponse(BaseModel):
    campaign_id: UUID
    assets: list[dict[str, Any]]
    count: int


class CampaignPerformanceResponse(BaseModel):
    campaign_id: UUID
    metrics: dict[str, float]
    time_series: list[dict[str, Any]]
    anomalies: list[dict[str, Any]]


class CampaignReportResponse(BaseModel):
    campaign_id: UUID
    format: Literal["json", "markdown", "pdf"]
    content: Any
    encoding: str | None = None


class CampaignOptimizeRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1200)
    budget_shift_pct: float | None = Field(default=None, ge=-100, le=100)
    target_channels: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=2000)


class CampaignOptimizeResponse(BaseModel):
    campaign_id: UUID
    status: str
    message: str


class CampaignDeleteResponse(BaseModel):
    campaign_id: UUID
    message: str


class QAMetricsInput(BaseModel):
    impressions: int = Field(..., ge=0)
    clicks: int = Field(..., ge=0)
    conversions: int = Field(..., ge=0)
    spend: float = Field(..., ge=0)
    revenue: float = Field(default=0, ge=0)
    unique_reach: int = Field(default=0, ge=0)
    objective: str = Field(default="conversion", min_length=3, max_length=40)
    campaign_duration_days: int = Field(default=30, ge=1, le=3650)


class CampaignQASimulateRequest(BaseModel):
    scenario: Literal[
        "content_zero_budget",
        "content_missing_audience",
        "media_low_budget_students",
        "media_high_budget",
        "media_invalid_budget",
        "performance_poor",
        "performance_excellent",
        "report_full",
    ]
    content_request: str | None = Field(default=None, min_length=5, max_length=2000)
    budget: float | None = Field(default=None, ge=0)
    audience: str | None = Field(default=None, min_length=2, max_length=300)
    metrics: QAMetricsInput | None = None


class CampaignQASimulateResponse(BaseModel):
    campaign_id: UUID
    status: str
    message: str
