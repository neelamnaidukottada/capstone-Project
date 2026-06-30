import json
import pathlib
import sys
from datetime import UTC, datetime, timedelta

import pytest
from langchain_core.messages import AIMessage

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.reporter import (  # noqa: E402
    FinalReport,
    campaign_reporter_node,
    export_report_json,
    export_report_markdown,
)


class FakeLLM:
    def __init__(self, responses):
        self._responses = responses
        self._idx = 0

    async def ainvoke(self, _messages):
        response = self._responses[self._idx]
        self._idx += 1
        if isinstance(response, Exception):
            raise response
        return AIMessage(content=response)


def _strategy_payload() -> dict:
    return {
        "objectives": ["Increase qualified pipeline by 25% in 90 days"],
        "target_audiences": [
            {
                "name": "Growth Manager",
                "segment": "B2B SaaS",
                "demographics": ["Age 28-45", "North America"],
                "pain_points": ["High CAC"],
                "motivations": ["Pipeline growth"],
            }
        ],
        "key_messages": ["Automate campaign execution with measurable ROI"],
        "recommended_channels": [
            {
                "channel": "Google Ads",
                "budget_percentage": 45,
                "rationale": "High intent capture",
                "execution_notes": ["Keyword expansion"],
            }
        ],
        "timeline": [
            {"day": 1, "title": "Kickoff", "description": "Launch", "success_criteria": "Tracking valid"}
        ],
        "budget_allocation": {"google_ads": 50000, "meta_ads": 30000, "linkedin_ads": 20000},
        "competitive_differentiation": ["Faster onboarding"],
        "confidence_score": 0.84,
    }


def _content_payload() -> dict:
    return {
        "assets": [
            {
                "asset_id": "asset_1",
                "asset_type": "ad_copy",
                "platform": "google_ads",
                "persona_name": "Growth Manager",
                "title": "Scale Pipeline Faster",
                "body": "Cut campaign launch time and improve conversion quality.",
                "cta": "Book Demo",
                "variant": "A",
                "day": None,
                "utm_parameters": {
                    "source": "google",
                    "medium": "cpc",
                    "campaign": "q3_growth",
                    "content": "asset_1",
                    "term": "pipeline automation",
                },
                "ab_test": {
                    "variant_a": "ROI-first",
                    "variant_b": "Pain-first",
                    "hypothesis": "ROI framing lifts CTR",
                },
                "metadata": {
                    "performance": {
                        "impressions": 12000,
                        "clicks": 350,
                        "conversions": 24,
                        "spend": 980,
                    }
                },
            },
            {
                "asset_id": "asset_2",
                "asset_type": "ad_copy",
                "platform": "meta_ads",
                "persona_name": "Growth Manager",
                "title": "Drive Better Leads",
                "body": "Improve conversion efficiency with AI-assisted workflows.",
                "cta": "Get Started",
                "variant": "B",
                "day": None,
                "utm_parameters": {
                    "source": "meta",
                    "medium": "paid_social",
                    "campaign": "q3_growth",
                    "content": "asset_2",
                    "term": None,
                },
                "ab_test": {
                    "variant_a": "Benefit-first",
                    "variant_b": "Urgency-first",
                    "hypothesis": "Urgency improves click-through",
                },
                "metadata": {
                    "performance": {
                        "impressions": 9000,
                        "clicks": 180,
                        "conversions": 8,
                        "spend": 820,
                    }
                },
            },
        ]
    }


def _media_plan_payload() -> dict:
    return {
        "channels": [
            {
                "channel": "google_ads",
                "budget": 50000,
                "budget_percentage": 50,
                "bid_strategy": "target CPA",
                "targeting": {
                    "demographics": ["Age 28-45"],
                    "interests": ["Growth marketing"],
                    "behaviors": ["B2B software research"],
                    "lookalike_audiences": ["MQL lookalike"],
                },
                "projected_reach": 350000,
                "projected_impressions": 620000,
                "projected_clicks": 15200,
                "projected_conversions": 920,
                "rationale": "Best intent capture",
            },
            {
                "channel": "meta_ads",
                "budget": 30000,
                "budget_percentage": 30,
                "bid_strategy": "maximize conversions",
                "targeting": {
                    "demographics": ["Age 25-44"],
                    "interests": ["Demand generation"],
                    "behaviors": ["Business tool buyers"],
                    "lookalike_audiences": ["Site visitors"],
                },
                "projected_reach": 410000,
                "projected_impressions": 780000,
                "projected_clicks": 9700,
                "projected_conversions": 520,
                "rationale": "Scale and retargeting",
            },
            {
                "channel": "linkedin_ads",
                "budget": 20000,
                "budget_percentage": 20,
                "bid_strategy": "manual CPC",
                "targeting": {
                    "demographics": ["Senior managers"],
                    "interests": ["Revenue operations"],
                    "behaviors": ["B2B SaaS decision makers"],
                    "lookalike_audiences": ["SQL lookalike"],
                },
                "projected_reach": 120000,
                "projected_impressions": 250000,
                "projected_clicks": 3100,
                "projected_conversions": 150,
                "rationale": "High-quality leads",
            },
        ],
        "total_budget": 100000,
        "daily_budget": 1666.67,
        "bid_strategy": "target CPA",
        "targeting": {
            "demographics": ["Age 25-45"],
            "interests": ["Growth"],
            "behaviors": ["Software buyers"],
            "lookalike_audiences": ["MQL lookalike"],
        },
        "flight_dates": {
            "start_date": "2026-06-01",
            "end_date": "2026-07-31",
            "dayparting_recommendations": ["Prioritize 9:00-18:00"],
        },
    }


def _performance_report_payload() -> dict:
    return {
        "metrics": {
            "ctr": 0.024,
            "cpc": 2.1,
            "cpa": 58,
            "roas": 3.1,
            "conversion_rate": 0.041,
            "frequency": 2.8,
            "spend": 91234,
        },
        "anomalies": [
            {
                "metric": "cpa",
                "method": "benchmark",
                "severity": "medium",
                "observed_value": 58,
                "expected_value": 52,
                "description": "CPA above benchmark in week 3",
                "channel": "meta_ads",
                "asset_id": "asset_2",
                "timestamp": "2026-06-20",
            }
        ],
        "recommendations": [
            {
                "category": "budget_reallocation",
                "action": "Shift 10% from meta to google",
                "rationale": "Google conversion quality is higher",
                "expected_impact": "Improve blended CPA",
                "priority": "high",
            },
            {
                "category": "creative_refresh",
                "action": "Refresh low CTR creatives in Meta",
                "rationale": "Signs of fatigue",
                "expected_impact": "Recover CTR",
                "priority": "medium",
            },
        ],
        "optimization_score": 0.79,
        "projected_end_of_campaign": {
            "projected_impressions": 1800000,
            "projected_clicks": 30000,
            "projected_conversions": 1800,
            "projected_spend": 104000,
            "projected_revenue": 318000,
            "projected_roas": 3.06,
        },
        "underperforming_channels": ["meta_ads"],
        "underperforming_assets": ["asset_2"],
    }


def _agent_logs_payload() -> list[dict]:
    now = datetime.now(UTC)
    return [
        {
            "agent_name": "strategic_planner",
            "action": "generate_strategy",
            "status": "completed",
            "started_at": (now - timedelta(seconds=5)).isoformat(),
            "completed_at": now.isoformat(),
            "latency_ms": 4200,
            "notes": "ok",
        },
        {
            "agent_name": "content_creator",
            "action": "generate_assets",
            "status": "completed",
            "started_at": (now - timedelta(seconds=9)).isoformat(),
            "completed_at": (now - timedelta(seconds=2)).isoformat(),
            "latency_ms": 6900,
            "notes": "ok",
        },
    ]


@pytest.mark.asyncio
async def test_campaign_reporter_node_returns_final_report_and_exports():
    llm = FakeLLM(
        [
            json.dumps(
                {
                    "executive_summary": "Campaign exceeded ROI targets with strong conversion efficiency and clear optimization learnings.",
                    "recommendations": [
                        "Scale high-intent channels by 15% next cycle.",
                        "Increase creative refresh cadence to weekly.",
                        "Tighten audience exclusions for low-quality cohorts.",
                    ],
                    "next_steps": [
                        "Finalize budget changes for next launch.",
                        "Publish weekly executive dashboards.",
                        "Run audience holdout tests.",
                    ],
                }
            )
        ]
    )

    result = await campaign_reporter_node(
        {
            "campaign_strategy": _strategy_payload(),
            "content_package": _content_payload(),
            "media_plan": _media_plan_payload(),
            "performance_report": _performance_report_payload(),
            "agent_logs": _agent_logs_payload(),
        },
        llm=llm,
    )

    assert result["agent_name"] == "campaign_reporter"
    assert "final_report" in result
    assert "report_exports" in result

    report = result["final_report"]
    assert len(report["detailed_sections"]) >= 6
    assert len(report["recommendations"]) >= 3
    assert len(report["next_steps"]) >= 3
    assert "spend_allocation_pie" in report["charts_data"]

    exports = result["report_exports"]
    assert "json" in exports
    assert "markdown" in exports
    assert "pdf" in exports


def test_report_export_json_and_markdown_helpers():
    final_report = FinalReport(
        executive_summary="Executive summary text",
        detailed_sections=[],
        charts_data={"k": []},
        recommendations=["Do X"],
        next_steps=["Step 1"],
    )

    as_json = export_report_json(final_report)
    assert isinstance(as_json, dict)
    assert as_json["executive_summary"] == "Executive summary text"

    as_md = export_report_markdown(final_report)
    assert "# Campaign Final Report" in as_md
    assert "## Executive Summary" in as_md
    assert "Do X" in as_md


def test_report_pdf_export_capability_signal():
    # This test validates capability behavior without forcing reportlab dependency.
    final_report = FinalReport(
        executive_summary="PDF test",
        detailed_sections=[],
        charts_data={},
        recommendations=[],
        next_steps=[],
    )

    from src.reporter import export_report_pdf_bytes

    try:
        pdf = export_report_pdf_bytes(final_report)
        assert isinstance(pdf, (bytes, bytearray))
        assert len(pdf) > 0
    except RuntimeError as exc:
        assert "reportlab" in str(exc).lower()


@pytest.mark.asyncio
async def test_report_contains_required_campaign_outcomes_and_channel_rankings():
    llm = FakeLLM(
        [
            json.dumps(
                {
                    "executive_summary": "Campaign closed with measurable efficiency gains.",
                    "recommendations": ["Maintain top-channel investment"],
                    "next_steps": ["Prepare next cycle budget"],
                }
            )
        ]
    )

    result = await campaign_reporter_node(
        {
            "campaign_strategy": _strategy_payload(),
            "content_package": _content_payload(),
            "media_plan": _media_plan_payload(),
            "performance_report": _performance_report_payload(),
            "agent_logs": _agent_logs_payload(),
        },
        llm=llm,
    )

    sections = result["final_report"]["detailed_sections"]
    detail_section = next((section for section in sections if section["title"] == "Detailed Performance"), None)
    budget_section = next((section for section in sections if section["title"] == "Budget Analysis"), None)

    assert detail_section is not None
    assert budget_section is not None

    detail_bullets = " ".join(detail_section["bullets"]).lower()
    budget_bullets = " ".join(budget_section["bullets"]).lower()

    assert "best performing channel" in detail_bullets
    assert "worst performing channel" in detail_bullets
    assert "roas" in budget_bullets
    assert "cpa" in budget_bullets

    json_export = result["report_exports"]["json"]
    assert "recommendations" in json_export
    assert result["final_report"]["recommendations"]
