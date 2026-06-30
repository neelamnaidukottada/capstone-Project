"""Agents router — trigger and monitor LangGraph agent runs."""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.models.agent import AgentRunCreate, AgentRunRead

router = APIRouter()


@router.post("/runs", response_model=AgentRunRead, status_code=status.HTTP_202_ACCEPTED)
async def start_agent_run(payload: AgentRunCreate):
    """Enqueue a new agent run for a campaign."""
    # TODO: dispatch to LangGraph runner via Celery / background task
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")


@router.get("/runs/{run_id}", response_model=AgentRunRead)
async def get_agent_run(run_id: UUID):
    """Get the status of an agent run."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")


@router.get("/runs/{run_id}/stream")
async def stream_agent_run(run_id: UUID):
    """Server-Sent Events stream for real-time agent output."""

    async def _event_generator():
        # TODO: subscribe to Redis pub/sub or Postgres LISTEN
        yield "data: {}\n\n"

    return StreamingResponse(_event_generator(), media_type="text/event-stream")
