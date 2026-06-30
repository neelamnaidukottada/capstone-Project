"""Campaign routes for autonomous lifecycle management."""
from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request

from app.core.rbac import require_organization, require_role
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.models.campaign import (
    CampaignApprovalRequest,
    CampaignApprovalResponse,
    CampaignContentResponse,
    CampaignCreateRequest,
    CampaignCreateResponse,
    CampaignDeleteResponse,
    CampaignListResponse,
    CampaignOptimizeRequest,
    CampaignOptimizeResponse,
    CampaignPerformanceResponse,
    CampaignReportResponse,
    CampaignStateResponse,
    CampaignStatusResponse,
)
from app.services.campaign_service import execute_workflow, report_as_format, store

router = APIRouter()
logger = get_logger(__name__)


@limiter.limit("20/minute")
@router.post("", response_model=CampaignCreateResponse)
async def create_campaign(
    request: Request,
    payload: CampaignCreateRequest,
    user: dict = Depends(require_role("manager")),
):
    """Create a new campaign from a user goal and trigger workflow execution."""
    org_id = str(user.get("organization_id") or "")
    if not org_id:
        raise HTTPException(status_code=403, detail="Organization context missing")

    record = await store.create_campaign(
        user_id=str(user["sub"]),
        organization_id=org_id,
        payload=payload.model_dump(),
    )
    asyncio.create_task(execute_workflow(record.id))

    logger.info("campaign_created", campaign_id=str(record.id), user_id=str(user["sub"]))
    return CampaignCreateResponse(campaign_id=record.id, status=record.status)


@limiter.limit("120/minute")
@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_organization),
):
    """List all campaigns for the organization with pagination."""
    org_id = str(user.get("organization_id") or "")
    if not org_id:
        raise HTTPException(status_code=403, detail="Organization context missing")

    campaigns = await store.list_campaigns_by_org(org_id, limit=limit, offset=offset)
    total = await store.count_campaigns(org_id)

    return CampaignListResponse(
        campaigns=[
            {
                "campaign_id": c.id,
                "name": c.name,
                "status": c.status,
                "current_agent": c.current_agent,
                "progress_percentage": c.progress_percentage,
                "estimated_completion": c.estimated_completion,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
                "pending_approval": c.pending_approval,
            }
            for c in campaigns
        ],
        total=total,
    )


@limiter.limit("120/minute")
@router.get("/{campaign_id}", response_model=CampaignStateResponse)
async def get_campaign(
    request: Request,
    campaign_id: UUID,
    user: dict = Depends(require_organization),
):
    """Retrieve campaign with current workflow state and available outputs."""
    record = await store.get_campaign(campaign_id)
    if record.organization_id != str(user.get("organization_id")):
        raise HTTPException(status_code=403, detail="Forbidden")

    return CampaignStateResponse(
        campaign_id=record.id,
        status=record.status,
        current_agent=record.current_agent,
        progress_percentage=record.progress_percentage,
        estimated_completion=record.estimated_completion,
        strategy=record.strategy,
        content=record.content,
        media_plan=record.media_plan,
        performance=record.performance,
        report=record.report,
        pending_approval=record.pending_approval,
        error=record.error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@limiter.limit("20/minute")
@router.delete("/{campaign_id}", response_model=CampaignDeleteResponse)
async def delete_campaign(
    request: Request,
    campaign_id: UUID,
    user: dict = Depends(require_role("manager")),
):
    """Delete a campaign and all runtime state for the current organization."""
    record = await store.get_campaign(campaign_id)
    if record.organization_id != str(user.get("organization_id")):
        raise HTTPException(status_code=403, detail="Forbidden")

    await store.delete_campaign(campaign_id)
    logger.info("campaign_deleted", campaign_id=str(campaign_id), user_id=str(user.get("sub") or ""))
    return CampaignDeleteResponse(campaign_id=campaign_id, message="Campaign deleted")


@limiter.limit("180/minute")
@router.get("/{campaign_id}/status", response_model=CampaignStatusResponse)
async def get_campaign_status(
    request: Request,
    campaign_id: UUID,
    user: dict = Depends(require_organization),
):
    """Get real-time workflow status and estimated completion."""
    record = await store.get_campaign(campaign_id)
    if record.organization_id != str(user.get("organization_id")):
        raise HTTPException(status_code=403, detail="Forbidden")

    return CampaignStatusResponse(
        campaign_id=record.id,
        status=record.status,
        current_agent=record.current_agent,
        progress_percentage=record.progress_percentage,
        estimated_completion=record.estimated_completion,
        error=record.error,
    )


@limiter.limit("30/minute")
@router.post("/{campaign_id}/approve", response_model=CampaignApprovalResponse)
async def approve_campaign_step(
    request: Request,
    campaign_id: UUID,
    payload: CampaignApprovalRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_role("manager")),
):
    """Submit human approval for strategy or media plan and resume workflow."""
    record = await store.get_campaign(campaign_id)
    if record.organization_id != str(user.get("organization_id")):
        raise HTTPException(status_code=403, detail="Forbidden")

    if payload.approval_type not in {"strategy", "media_plan"}:
        raise HTTPException(status_code=400, detail="Unsupported approval_type")

    record.approvals[payload.approval_type] = payload.approved
    pending = None if payload.approved else {"type": payload.approval_type, "feedback": payload.feedback}
    await store.update_campaign(campaign_id, approvals=record.approvals, pending_approval=pending)

    background_tasks.add_task(execute_workflow, campaign_id)

    message = "Approval recorded and workflow resumed" if payload.approved else "Approval rejected"
    return CampaignApprovalResponse(campaign_id=campaign_id, status="running", message=message)


@limiter.limit("120/minute")
@router.get("/{campaign_id}/content", response_model=CampaignContentResponse)
async def get_campaign_content(
    request: Request,
    campaign_id: UUID,
    user: dict = Depends(require_organization),
):
    """Retrieve all generated campaign content assets."""
    record = await store.get_campaign(campaign_id)
    if record.organization_id != str(user.get("organization_id")):
        raise HTTPException(status_code=403, detail="Forbidden")

    assets = (record.content or {}).get("assets", [])
    return CampaignContentResponse(campaign_id=campaign_id, assets=assets, count=len(assets))


@limiter.limit("120/minute")
@router.get("/{campaign_id}/performance", response_model=CampaignPerformanceResponse)
async def get_campaign_performance(
    request: Request,
    campaign_id: UUID,
    user: dict = Depends(require_organization),
):
    """Retrieve real-time performance metrics and chart-ready time series."""
    record = await store.get_campaign(campaign_id)
    if record.organization_id != str(user.get("organization_id")):
        raise HTTPException(status_code=403, detail="Forbidden")

    perf = record.performance or {}
    return CampaignPerformanceResponse(
        campaign_id=campaign_id,
        metrics=perf.get("metrics", {}),
        time_series=perf.get("time_series", []),
        anomalies=perf.get("anomalies", []),
    )


@limiter.limit("60/minute")
@router.get("/{campaign_id}/report", response_model=CampaignReportResponse)
async def get_campaign_report(
    request: Request,
    campaign_id: UUID,
    background_tasks: BackgroundTasks,
    format: str = Query(default="json", pattern="^(json|markdown|pdf)$"),
    user: dict = Depends(require_organization),
):
    """Generate or retrieve final campaign report with json/markdown/pdf support."""
    record = await store.get_campaign(campaign_id)
    if record.organization_id != str(user.get("organization_id")):
        raise HTTPException(status_code=403, detail="Forbidden")

    if record.report is None:
        background_tasks.add_task(execute_workflow, campaign_id, manual_report_trigger=True)
        raise HTTPException(status_code=409, detail="Report not ready. Generation has been triggered.")

    rendered = report_as_format(record.report, format)
    return CampaignReportResponse(campaign_id=campaign_id, **rendered)


@limiter.limit("30/minute")
@router.post("/{campaign_id}/optimize", response_model=CampaignOptimizeResponse)
async def optimize_campaign(
    request: Request,
    campaign_id: UUID,
    payload: CampaignOptimizeRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_role("manager")),
):
    """Trigger a manual optimization cycle with optional optimization parameters."""
    record = await store.get_campaign(campaign_id)
    if record.organization_id != str(user.get("organization_id")):
        raise HTTPException(status_code=403, detail="Forbidden")

    logger.info(
        "campaign_optimization_requested",
        campaign_id=str(campaign_id),
        reason=payload.reason,
        budget_shift_pct=payload.budget_shift_pct,
        target_channels=payload.target_channels,
    )

    background_tasks.add_task(execute_workflow, campaign_id)
    return CampaignOptimizeResponse(
        campaign_id=campaign_id,
        status="running",
        message="Optimization cycle started",
    )
