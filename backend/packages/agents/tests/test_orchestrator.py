import pathlib
import sys
from datetime import UTC, datetime, timedelta

import pytest
from langchain_core.messages import HumanMessage

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.orchestrator import build_campaign_workflow, run_campaign_workflow_once


def _base_state() -> dict:
    return {
        "messages": [HumanMessage(content="Launch a B2B pipeline growth campaign")],
        "current_agent": None,
        "strategy": None,
        "content": None,
        "media_plan": None,
        "performance": None,
        "report": None,
        "status": "running",
        "error": None,
        "campaign_goal": {
            "goal": "Increase qualified pipeline by 25% in 90 days",
            "budget": 100000,
            "timeline_days": 90,
            "industry": "B2B SaaS",
            "product_description": "AI campaign automation platform for growth teams",
        },
        "brand_guidelines": {
            "tone": "clear",
            "voice": "expert",
            "prohibited_words": [],
            "brand_colors": ["#123456", "#abcdef"],
        },
        "total_budget": 100000,
        "campaign_execution_data": {
            "impressions": 200000,
            "clicks": 6000,
            "conversions": 260,
            "spend": 24000,
            "revenue": 84000,
            "unique_reach": 90000,
            "objective": "conversion",
            "campaign_duration_days": 30,
            "target_metrics": {"roas": 2.5},
            "time_series_data": [],
        },
        "agent_logs": [
            {
                "agent_name": "strategic_planner",
                "action": "generate_strategy",
                "status": "completed",
                "started_at": (datetime.now(UTC) - timedelta(seconds=5)).isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "latency_ms": 4100,
            }
        ],
        "retry_counts": {},
        "last_failed_agent": None,
        "planner_feedback": None,
        "strategy_confidence_threshold": 0.7,
        "monitor_interval_hours": 6,
        "next_monitor_at": None,
        "monitor_cycles": 0,
        "max_monitor_cycles": 1,
        "strategy_approved": True,
        "budget_approved": True,
        "human_in_the_loop": True,
        "auto_approve": True,
        "pending_approval": None,
        "manual_report_trigger": False,
        "campaign_complete": False,
    }


def _deps_happy_path() -> dict:
    async def planner(_state):
        return {
            "campaign_strategy": {
                "objectives": ["Increase pipeline"],
                "target_audiences": [
                    {
                        "name": "Ops Leader",
                        "segment": "B2B",
                        "demographics": ["US"],
                        "pain_points": ["Manual work"],
                        "motivations": ["Efficiency"],
                    },
                    {
                        "name": "Rev Manager",
                        "segment": "B2B",
                        "demographics": ["EU"],
                        "pain_points": ["CAC"],
                        "motivations": ["Growth"],
                    },
                ],
                "key_messages": ["Automate campaigns"],
                "recommended_channels": [
                    {
                        "channel": "google_ads",
                        "budget_percentage": 50,
                        "rationale": "intent",
                        "execution_notes": [],
                    }
                ],
                "timeline": [
                    {
                        "day": 1,
                        "title": "Kickoff",
                        "description": "Start",
                        "success_criteria": "Tracking ok",
                    }
                ],
                "budget_allocation": {"google_ads": 100000},
                "competitive_differentiation": ["speed"],
                "confidence_score": 0.82,
            },
            "planner_confidence": 0.82,
        }

    async def content_creator(_state):
        return {
            "content_package": {
                "assets": [
                    {
                        "asset_id": "asset-1",
                        "asset_type": "ad_copy",
                        "platform": "google_ads",
                        "persona_name": "Ops Leader",
                        "title": "Scale Faster",
                        "body": "Get more qualified leads",
                        "cta": "Book Demo",
                        "variant": "A",
                        "utm_parameters": {
                            "source": "google",
                            "medium": "cpc",
                            "campaign": "launch",
                            "content": "asset-1",
                            "term": None,
                        },
                        "ab_test": {
                            "variant_a": "ROI",
                            "variant_b": "Speed",
                            "hypothesis": "ROI framing improves CTR",
                        },
                        "metadata": {},
                    }
                ]
            },
            "content_valid": True,
            "content_quality_issues": [],
        }

    async def media_buyer(_state):
        return {
            "media_plan": {
                "channels": [
                    {
                        "channel": "google_ads",
                        "budget": 100000,
                        "budget_percentage": 100,
                        "bid_strategy": "target CPA",
                        "targeting": {
                            "demographics": ["US"],
                            "interests": ["Growth"],
                            "behaviors": ["Buyer"],
                            "lookalike_audiences": ["MQL"],
                        },
                        "projected_reach": 100000,
                        "projected_impressions": 300000,
                        "projected_clicks": 7000,
                        "projected_conversions": 290,
                        "rationale": "high intent",
                    }
                ],
                "total_budget": 100000,
                "daily_budget": 3333.33,
                "bid_strategy": "target CPA",
                "targeting": {
                    "demographics": ["US"],
                    "interests": ["Growth"],
                    "behaviors": ["Buyer"],
                    "lookalike_audiences": ["MQL"],
                },
                "flight_dates": {
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-30",
                    "dayparting_recommendations": ["09:00-18:00"],
                },
            },
            "media_plan_valid": True,
            "media_plan_issues": [],
        }

    async def performance_analyst(_state):
        return {
            "performance_report": {
                "metrics": {"roas": 3.0, "ctr": 0.024, "cpa": 58.0},
                "anomalies": [],
                "recommendations": [
                    {
                        "category": "budget_reallocation",
                        "action": "Shift 10% to top channel",
                        "rationale": "higher conversion efficiency",
                        "expected_impact": "Improve blended CPA",
                        "priority": "high",
                    }
                ],
                "optimization_score": 0.81,
                "projected_end_of_campaign": {
                    "projected_revenue": 320000,
                    "projected_spend": 105000,
                    "projected_roas": 3.05,
                },
                "underperforming_channels": [],
                "underperforming_assets": [],
            }
        }

    async def reporter(_state):
        return {
            "final_report": {
                "executive_summary": "Campaign exceeded efficiency targets.",
                "detailed_sections": [],
                "charts_data": {"spend_allocation_pie": []},
                "recommendations": ["Scale winner channels"],
                "next_steps": ["Approve next budget plan"],
            }
        }

    return {
        "planner": planner,
        "content_creator": content_creator,
        "media_buyer": media_buyer,
        "performance_analyst": performance_analyst,
        "reporter": reporter,
    }


@pytest.mark.asyncio
async def test_campaign_workflow_happy_path_completes_with_report():
    result = await run_campaign_workflow_once(_base_state(), deps=_deps_happy_path())

    assert result["status"] == "completed"
    assert result["report"] is not None
    assert result["current_agent"] == "campaign_reporter"


@pytest.mark.asyncio
async def test_campaign_workflow_low_confidence_retries_then_succeeds():
    state = _base_state()
    planner_calls = {"count": 0}

    async def planner(_state):
        planner_calls["count"] += 1
        confidence = 0.62 if planner_calls["count"] == 1 else 0.85
        return {
            "campaign_strategy": {
                "objectives": ["Increase pipeline"],
                "target_audiences": [
                    {
                        "name": "Ops Leader",
                        "segment": "B2B",
                        "demographics": ["US"],
                        "pain_points": ["Manual"],
                        "motivations": ["Scale"],
                    },
                    {
                        "name": "Rev Manager",
                        "segment": "B2B",
                        "demographics": ["EU"],
                        "pain_points": ["CAC"],
                        "motivations": ["ROI"],
                    },
                ],
                "key_messages": ["Automate"],
                "recommended_channels": [
                    {
                        "channel": "google_ads",
                        "budget_percentage": 100,
                        "rationale": "intent",
                        "execution_notes": [],
                    }
                ],
                "timeline": [
                    {
                        "day": 1,
                        "title": "Kickoff",
                        "description": "Start",
                        "success_criteria": "ok",
                    }
                ],
                "budget_allocation": {"google_ads": 100000},
                "competitive_differentiation": ["speed"],
                "confidence_score": confidence,
            }
        }

    deps = _deps_happy_path()
    deps["planner"] = planner

    result = await run_campaign_workflow_once(state, deps=deps)

    assert result["status"] == "completed"
    assert planner_calls["count"] >= 2


@pytest.mark.asyncio
async def test_campaign_workflow_escalates_after_three_failures():
    state = _base_state()
    state["strategy_approved"] = False
    state["auto_approve"] = False

    async def planner(_state):
        return {"campaign_strategy": None, "planner_error": "upstream timeout"}

    deps = _deps_happy_path()
    deps["planner"] = planner

    result = await run_campaign_workflow_once(state, deps=deps)

    assert result["status"] == "awaiting_human_approval"
    assert result["retry_counts"]["strategic_planner"] >= 3
    assert result["pending_approval"] is not None


@pytest.mark.asyncio
async def test_campaign_workflow_human_budget_checkpoint_pauses():
    state = _base_state()
    state["auto_approve"] = False
    state["strategy_approved"] = True
    state["budget_approved"] = False

    result = await run_campaign_workflow_once(state, deps=_deps_happy_path())

    assert result["status"] == "awaiting_human_approval"
    assert result["pending_approval"]["type"] == "media_plan"


def test_graph_name_and_structure_compile():
    graph = build_campaign_workflow(deps=_deps_happy_path())
    compiled = graph.compile(name="campaign_workflow")
    assert compiled is not None
