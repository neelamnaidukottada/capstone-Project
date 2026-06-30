"""Central LangGraph orchestrator for the campaign lifecycle.

Graph name: campaign_workflow
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except Exception:  # pragma: no cover - optional dependency at runtime
    AsyncPostgresSaver = None  # type: ignore[assignment]

from .content_creator import content_creator_node
from .media_buyer import media_buyer_node
from .performance_analyst import performance_analyst_node
from .planner import strategic_planner_node
from .reporter import campaign_reporter_node

GRAPH_NAME = "campaign_workflow"

AgentNode = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def reduce_optional_str(current: str | None, update: str | None) -> str | None:
    return update if update is not None else current


def reduce_optional_dict(current: dict[str, Any] | None, update: dict[str, Any] | None) -> dict[str, Any] | None:
    return update if update is not None else current


def reduce_optional_list(current: list[Any] | None, update: list[Any] | None) -> list[Any] | None:
    return update if update is not None else current


def reduce_status(current: str, update: str) -> str:
    return update or current


def reduce_retry_counts(current: dict[str, int], update: dict[str, int]) -> dict[str, int]:
    merged = dict(current)
    for key, value in update.items():
        merged[key] = max(0, int(value))
    return merged


class CampaignState(TypedDict, total=False):
    # Required schema fields
    messages: Annotated[list[BaseMessage], add_messages]
    current_agent: Annotated[str | None, reduce_optional_str]
    strategy: Annotated[dict[str, Any] | None, reduce_optional_dict]
    content: Annotated[dict[str, Any] | None, reduce_optional_dict]
    media_plan: Annotated[dict[str, Any] | None, reduce_optional_dict]
    performance: Annotated[dict[str, Any] | None, reduce_optional_dict]
    report: Annotated[dict[str, Any] | None, reduce_optional_dict]
    status: Annotated[str, reduce_status]
    error: Annotated[str | None, reduce_optional_str]

    # Control and integration fields
    campaign_goal: dict[str, Any]
    content_request: str | None
    brand_guidelines: dict[str, Any]
    total_budget: float | dict[str, Any]
    campaign_execution_data: dict[str, Any]
    agent_logs: list[dict[str, Any]]

    retry_counts: Annotated[dict[str, int], reduce_retry_counts]
    last_failed_agent: Annotated[str | None, reduce_optional_str]
    planner_feedback: Annotated[str | None, reduce_optional_str]

    strategy_confidence_threshold: float
    monitor_interval_hours: int
    next_monitor_at: str | None
    monitor_cycles: int
    max_monitor_cycles: int

    strategy_approved: bool
    budget_approved: bool
    human_in_the_loop: bool
    auto_approve: bool
    pending_approval: Annotated[dict[str, Any] | None, reduce_optional_dict]

    manual_report_trigger: bool
    campaign_complete: bool


class CampaignWorkflowDependencies(TypedDict, total=False):
    planner: AgentNode
    content_creator: AgentNode
    media_buyer: AgentNode
    performance_analyst: AgentNode
    reporter: AgentNode


def _default_deps() -> CampaignWorkflowDependencies:
    return {
        "planner": strategic_planner_node,
        "content_creator": content_creator_node,
        "media_buyer": media_buyer_node,
        "performance_analyst": performance_analyst_node,
        "reporter": campaign_reporter_node,
    }


def _safe_retry_counts(state: CampaignState) -> dict[str, int]:
    return dict(state.get("retry_counts", {}))


def _increment_failure(state: CampaignState, agent_name: str, error: str) -> dict[str, Any]:
    counts = _safe_retry_counts(state)
    counts[agent_name] = counts.get(agent_name, 0) + 1
    return {
        "retry_counts": counts,
        "last_failed_agent": agent_name,
        "error": error,
        "status": f"failed:{agent_name}",
    }


def _is_agent_escalated(state: CampaignState) -> bool:
    agent = state.get("last_failed_agent")
    if not agent:
        return False
    return _safe_retry_counts(state).get(agent, 0) >= 3


def _build_approval_payload(kind: Literal["strategy", "budget"], state: CampaignState) -> dict[str, Any]:
    if kind == "strategy":
        return {
            "type": "strategy",
            "title": "Approve Campaign Strategy",
            "summary": "Review strategy confidence, objectives, channels, and timeline.",
            "strategy": state.get("strategy"),
            "ui_component": "StrategyApprovalPanel",
            "approved": state.get("strategy_approved", False),
        }

    return {
        "type": "media_plan",
        "title": "Approve Budget Allocation",
        "summary": "Review channel budget split and projected outcomes.",
        "media_plan": state.get("media_plan"),
        "ui_component": "BudgetAllocationPanel",
        "approved": state.get("budget_approved", False),
    }


async def _supervisor_node(state: CampaignState) -> dict[str, Any]:
    return {
        "current_agent": "supervisor",
        "status": state.get("status", "running"),
    }


async def _planner_node(state: CampaignState, deps: CampaignWorkflowDependencies) -> dict[str, Any]:
    planner = deps["planner"]
    planner_state = {
        "campaign_goal": state.get("campaign_goal"),
    }
    if state.get("planner_feedback"):
        planner_state["planner_feedback"] = state["planner_feedback"]

    try:
        patch = await planner(planner_state)
    except Exception as exc:
        return _increment_failure(state, "strategic_planner", str(exc))

    strategy = patch.get("campaign_strategy")
    if strategy is None:
        reason = patch.get("planner_error", "planner returned no strategy")
        return _increment_failure(state, "strategic_planner", str(reason))

    return {
        "current_agent": "strategic_planner",
        "strategy": strategy,
        "status": "strategy_ready",
        "error": None,
    }


async def _content_creator_node(state: CampaignState, deps: CampaignWorkflowDependencies) -> dict[str, Any]:
    node = deps["content_creator"]
    try:
        patch = await node(
            {
                "campaign_strategy": state.get("strategy"),
                "brand_guidelines": state.get("brand_guidelines"),
                "content_request": state.get("content_request"),
                "total_budget": state.get("total_budget", 0.0),
            }
        )
    except Exception as exc:
        return _increment_failure(state, "content_creator", str(exc))

    if patch.get("content_package") is None or not patch.get("content_valid", False):
        reason = patch.get("content_error", "content generation failed validation")
        return _increment_failure(state, "content_creator", str(reason))

    content_package = dict(patch["content_package"])
    if patch.get("content_assumptions"):
        content_package["assumptions"] = patch["content_assumptions"]

    return {
        "current_agent": "content_creator",
        "content": content_package,
        "status": "content_ready",
        "error": None,
    }


async def _media_buyer_node(state: CampaignState, deps: CampaignWorkflowDependencies) -> dict[str, Any]:
    node = deps["media_buyer"]
    try:
        patch = await node(
            {
                "campaign_strategy": state.get("strategy"),
                "content_package": state.get("content"),
                "total_budget": state.get("total_budget", 0.0),
            }
        )
    except Exception as exc:
        return _increment_failure(state, "media_buyer", str(exc))

    if patch.get("media_plan") is None or not patch.get("media_plan_valid", False):
        reason = patch.get("media_plan_error", "media plan invalid")
        return _increment_failure(state, "media_buyer", str(reason))

    return {
        "current_agent": "media_buyer",
        "media_plan": patch["media_plan"],
        "status": "media_plan_ready",
        "error": None,
    }


def _build_execution_data_from_state(state: CampaignState) -> dict[str, Any] | None:
    raw = state.get("campaign_execution_data")
    if raw:
        return raw

    media = state.get("media_plan") or {}
    channels = media.get("channels") or []
    if not channels:
        return None

    impressions = int(sum(float(ch.get("projected_impressions", 0)) for ch in channels))
    clicks = int(sum(float(ch.get("projected_clicks", 0)) for ch in channels))
    conversions = int(sum(float(ch.get("projected_conversions", 0)) for ch in channels))
    spend = float(media.get("total_budget", state.get("total_budget", 0.0) or 0.0))
    revenue = float(spend * 3.0)
    unique_reach = int(sum(float(ch.get("projected_reach", 0)) for ch in channels))

    return {
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "spend": spend,
        "revenue": revenue,
        "unique_reach": unique_reach,
        "objective": "conversion",
        "campaign_duration_days": 30,
        "target_metrics": {},
        "time_series_data": [],
    }


async def _performance_analyst_node(state: CampaignState, deps: CampaignWorkflowDependencies) -> dict[str, Any]:
    node = deps["performance_analyst"]
    execution_data = _build_execution_data_from_state(state)
    if execution_data is None:
        return {
            "status": "waiting_for_metrics",
            "error": None,
        }

    try:
        patch = await node({"campaign_execution_data": execution_data})
    except Exception as exc:
        return _increment_failure(state, "performance_analyst", str(exc))

    perf = patch.get("performance_report")
    if perf is None:
        return _increment_failure(state, "performance_analyst", "missing performance report")

    monitor_hours = int(state.get("monitor_interval_hours", 6))
    next_monitor_at = (datetime.now(UTC) + timedelta(hours=max(1, monitor_hours))).isoformat()

    return {
        "current_agent": "performance_analyst",
        "performance": perf,
        "next_monitor_at": next_monitor_at,
        "monitor_cycles": int(state.get("monitor_cycles", 0)) + 1,
        "status": "performance_ready",
        "error": None,
    }


async def _reporter_node(state: CampaignState, deps: CampaignWorkflowDependencies) -> dict[str, Any]:
    node = deps["reporter"]

    try:
        patch = await node(
            {
                "campaign_strategy": state.get("strategy"),
                "content_package": state.get("content"),
                "media_plan": state.get("media_plan"),
                "performance_report": state.get("performance"),
                "agent_logs": state.get("agent_logs", []),
            }
        )
    except Exception as exc:
        return _increment_failure(state, "campaign_reporter", str(exc))

    report = patch.get("final_report")
    if report is None:
        return _increment_failure(state, "campaign_reporter", "reporter returned no final report")

    return {
        "current_agent": "campaign_reporter",
        "report": report,
        "status": "completed",
        "error": None,
        "campaign_complete": True,
    }


async def _parallel_entry_node(_state: CampaignState) -> dict[str, Any]:
    return {"status": "running_parallel_generation"}


async def _human_checkpoint_node(state: CampaignState) -> dict[str, Any]:
    if state.get("pending_approval"):
        return {
            "status": "awaiting_human_approval",
            "current_agent": "human_checkpoint",
        }
    return {
        "status": state.get("status", "running"),
    }


def _get_strategy_confidence(state: CampaignState) -> float:
    strategy = state.get("strategy") or {}
    value = strategy.get("confidence_score", 0.0)
    try:
        return float(value)
    except Exception:
        return 0.0


def _should_wait_for_strategy_approval(state: CampaignState) -> bool:
    if not state.get("human_in_the_loop", False):
        return False
    if state.get("auto_approve", False):
        return False
    if state.get("strategy_approved", False):
        return False
    return True


def _should_wait_for_budget_approval(state: CampaignState) -> bool:
    if not state.get("human_in_the_loop", False):
        return False
    if state.get("auto_approve", False):
        return False
    if state.get("budget_approved", False):
        return False
    return True


SupervisorRoute = Literal[
    "run_planner",
    "run_planner_retry",
    "wait_human",
    "run_parallel",
    "run_performance",
    "run_reporter",
    "end",
]


async def _prepare_approval_payloads(state: CampaignState) -> dict[str, Any]:
    if _should_wait_for_strategy_approval(state):
        return {
            "pending_approval": _build_approval_payload("strategy", state),
            "status": "awaiting_strategy_approval",
            "current_agent": "supervisor",
        }

    if _should_wait_for_budget_approval(state):
        return {
            "pending_approval": _build_approval_payload("budget", state),
            "status": "awaiting_budget_approval",
            "current_agent": "supervisor",
        }

    return {
        "pending_approval": None,
        "status": state.get("status", "running"),
        "current_agent": "supervisor",
    }


def _supervisor_route(state: CampaignState) -> SupervisorRoute:
    if _is_agent_escalated(state):
        return "wait_human"

    if state.get("report") is not None:
        return "end"

    if state.get("strategy") is None:
        return "run_planner"

    confidence = _get_strategy_confidence(state)
    threshold = float(state.get("strategy_confidence_threshold", 0.7))
    if confidence < threshold:
        counts = _safe_retry_counts(state)
        attempts = counts.get("strategic_planner", 0)
        if attempts >= 3:
            return "wait_human"
        return "run_planner_retry"

    if _should_wait_for_strategy_approval(state) or _should_wait_for_budget_approval(state):
        return "wait_human"

    if state.get("content") is None or state.get("media_plan") is None:
        return "run_parallel"

    if state.get("performance") is None:
        return "run_performance"

    if state.get("manual_report_trigger", False) or state.get("campaign_complete", False):
        return "run_reporter"

    max_cycles = int(state.get("max_monitor_cycles", 1))
    cycles = int(state.get("monitor_cycles", 0))
    if cycles >= max_cycles:
        return "run_reporter"

    next_monitor_raw = state.get("next_monitor_at")
    if not next_monitor_raw:
        return "run_performance"

    try:
        next_monitor_at = datetime.fromisoformat(next_monitor_raw)
    except Exception:
        return "run_performance"

    if datetime.now(UTC) >= next_monitor_at:
        return "run_performance"

    return "end"


def _route_human_checkpoint(_state: CampaignState) -> Literal["end"]:
    return "end"


def _route_parallel(_state: CampaignState) -> list[Literal["content_creator", "media_buyer"]]:
    return ["content_creator", "media_buyer"]


def build_campaign_workflow(
    deps: CampaignWorkflowDependencies | None = None,
) -> StateGraph:
    """Build the central lifecycle graph definition."""
    resolved_deps = _default_deps()
    if deps:
        resolved_deps.update(deps)

    async def _strategic_planner_wrapped(state: CampaignState) -> dict[str, Any]:
        return await _planner_node(state, resolved_deps)

    async def _content_creator_wrapped(state: CampaignState) -> dict[str, Any]:
        return await _content_creator_node(state, resolved_deps)

    async def _media_buyer_wrapped(state: CampaignState) -> dict[str, Any]:
        return await _media_buyer_node(state, resolved_deps)

    async def _performance_analyst_wrapped(state: CampaignState) -> dict[str, Any]:
        return await _performance_analyst_node(state, resolved_deps)

    async def _campaign_reporter_wrapped(state: CampaignState) -> dict[str, Any]:
        return await _reporter_node(state, resolved_deps)

    graph = StateGraph(CampaignState)

    graph.add_node("supervisor", _supervisor_node)
    graph.add_node("strategic_planner", _strategic_planner_wrapped)
    graph.add_node("parallel_entry", _parallel_entry_node)
    graph.add_node("content_creator", _content_creator_wrapped)
    graph.add_node("media_buyer", _media_buyer_wrapped)
    graph.add_node("performance_analyst", _performance_analyst_wrapped)
    graph.add_node("campaign_reporter", _campaign_reporter_wrapped)
    graph.add_node("human_checkpoint", _human_checkpoint_node)
    graph.add_node("prepare_approval", _prepare_approval_payloads)

    graph.add_edge(START, "supervisor")

    graph.add_conditional_edges(
        "supervisor",
        _supervisor_route,
        {
            "run_planner": "strategic_planner",
            "run_planner_retry": "strategic_planner",
            "wait_human": "prepare_approval",
            "run_parallel": "parallel_entry",
            "run_performance": "performance_analyst",
            "run_reporter": "campaign_reporter",
            "end": END,
        },
    )

    graph.add_edge("strategic_planner", "supervisor")

    graph.add_conditional_edges(
        "parallel_entry",
        _route_parallel,
        {
            "content_creator": "content_creator",
            "media_buyer": "media_buyer",
        },
    )
    graph.add_edge("content_creator", "supervisor")
    graph.add_edge("media_buyer", "supervisor")

    graph.add_edge("performance_analyst", "supervisor")
    graph.add_edge("campaign_reporter", END)

    graph.add_edge("prepare_approval", "human_checkpoint")
    graph.add_conditional_edges("human_checkpoint", _route_human_checkpoint, {"end": END})

    return graph


def build_supabase_checkpointer(supabase_db_url: str) -> dict[str, str]:
    """Return checkpoint configuration for Supabase Postgres persistence.

    The runtime checkpointer instance is created inside run_campaign_workflow.
    """
    return {
        "provider": "supabase_postgres",
        "connection_url": supabase_db_url,
    }


async def run_campaign_workflow(
    initial_state: CampaignState,
    *,
    thread_id: str,
    supabase_db_url: str | None = None,
    deps: CampaignWorkflowDependencies | None = None,
) -> CampaignState:
    """Execute the campaign workflow end-to-end.

    If supabase_db_url is provided, graph checkpoints are persisted after each node.
    """
    graph = build_campaign_workflow(deps=deps)
    config = {"configurable": {"thread_id": thread_id}}

    if supabase_db_url:
        if AsyncPostgresSaver is None:
            raise RuntimeError(
                "Supabase checkpointing requires langgraph Postgres checkpointer extras. "
                "Install with: pip install langgraph-checkpoint-postgres"
            )
        async with await AsyncPostgresSaver.from_conn_string(supabase_db_url) as checkpointer:
            await checkpointer.setup()
            compiled = graph.compile(name=GRAPH_NAME, checkpointer=checkpointer)
            result = await compiled.ainvoke(initial_state, config=config)
            return result

    compiled = graph.compile(name=GRAPH_NAME)
    result = await compiled.ainvoke(initial_state, config=config)
    return result


async def run_campaign_workflow_once(
    state: CampaignState,
    *,
    deps: CampaignWorkflowDependencies | None = None,
) -> CampaignState:
    """Convenience helper for tests/local runs without checkpointing."""
    return await run_campaign_workflow(
        initial_state=state,
        thread_id="local-thread",
        deps=deps,
        supabase_db_url=None,
    )


async def run_campaign_workflow_loop(
    state: CampaignState,
    *,
    deps: CampaignWorkflowDependencies | None = None,
    iterations: int = 3,
) -> CampaignState:
    """Run workflow repeatedly to emulate periodic monitoring cycles in tests."""
    current = state
    for idx in range(iterations):
        current = await run_campaign_workflow(
            initial_state=current,
            thread_id=f"loop-{idx}",
            deps=deps,
            supabase_db_url=None,
        )
        await asyncio.sleep(0)
    return current
