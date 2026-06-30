"""Campaign Reporter LangGraph node.

Generates an executive-ready final report from strategy, content, media, performance,
and agent execution logs.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError

from .content_creator import ContentPackage
from .media_buyer import MediaPlan
from .performance_analyst import PerformanceReport
from .planner import CampaignStrategy

logger = logging.getLogger(__name__)

AGENT_NAME = "campaign_reporter"


class AgentLogEntry(BaseModel):
    agent_name: str
    action: str
    status: str = "completed"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    latency_ms: int | None = None
    notes: str | None = None


class Section(BaseModel):
    title: str
    summary: str
    bullets: list[str] = Field(default_factory=list)
    table_headers: list[str] = Field(default_factory=list)
    table_rows: list[dict[str, Any]] = Field(default_factory=list)


class FinalReport(BaseModel):
    executive_summary: str
    detailed_sections: list[Section]
    charts_data: dict[str, Any]
    recommendations: list[str]
    next_steps: list[str]


class LLMReportEnvelope(BaseModel):
    executive_summary: str
    recommendations: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


SYSTEM_PROMPT = """You are a VP-level marketing and executive reporting strategist.

Your job is to produce concise, high-signal campaign reporting language for leadership.
Write in a clear, decisive, business tone.

Requirements:
- Highlight outcomes, ROI, and business impact.
- Mention lessons learned and strategic implications.
- Keep recommendations specific and actionable.
- Keep next steps prioritized and sequence-aware.

Output strict JSON only matching schema.
"""


SECTION_TEMPLATES: dict[str, dict[str, str]] = {
    "detailed_performance": {
        "title": "Detailed Performance",
        "summary": "Channel-by-channel delivery and efficiency metrics.",
    },
    "content_performance": {
        "title": "Content Performance",
        "summary": "Top and bottom creative assets based on efficiency and conversion impact.",
    },
    "budget_analysis": {
        "title": "Budget Analysis",
        "summary": "Planned versus actual spend, allocation variance, and cost efficiency.",
    },
    "audience_insights": {
        "title": "Audience Insights",
        "summary": "Audience cohorts that over-indexed or under-indexed in response quality.",
    },
    "competitive_analysis": {
        "title": "Competitive Analysis",
        "summary": "Performance versus objective-aligned industry benchmarks.",
    },
    "recommendations": {
        "title": "Recommendations",
        "summary": "Actionable actions for future campaign cycles.",
    },
}


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o",
        temperature=0.2,
        model_kwargs={"response_format": _json_schema_response_format()},
    )


def _json_schema_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "campaign_report_envelope",
            "schema": LLMReportEnvelope.model_json_schema(),
            "strict": True,
        },
    }


def _parse_llm_content(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        return json.loads(content)
    if isinstance(content, list):
        joined = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return json.loads(joined)
    raise ValueError("Unsupported LLM content format")


def _channel_performance_rows(media_plan: MediaPlan) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for channel in media_plan.channels:
        rows.append(
            {
                "channel": channel.channel,
                "budget": round(channel.budget, 2),
                "budget_pct": round(channel.budget_percentage, 2),
                "impressions": channel.projected_impressions,
                "reach": channel.projected_reach,
                "clicks": channel.projected_clicks,
                "conversions": channel.projected_conversions,
                "bid_strategy": channel.bid_strategy,
            }
        )
    return rows


def _asset_performance_rows(content_package: ContentPackage) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for asset in content_package.assets:
        perf = asset.metadata.get("performance", {})
        impressions = float(perf.get("impressions", 0))
        clicks = float(perf.get("clicks", 0))
        conversions = float(perf.get("conversions", 0))
        spend = float(perf.get("spend", 0))

        ctr = _safe_div(clicks, impressions)
        cpa = _safe_div(spend, conversions)
        score = (conversions * 4.0) + (ctr * 100.0) - (cpa * 0.1)

        rows.append(
            {
                "asset_id": asset.asset_id,
                "platform": asset.platform.value,
                "persona": asset.persona_name,
                "variant": asset.variant,
                "ctr": round(ctr, 4),
                "conversions": int(conversions),
                "cpa": round(cpa, 2),
                "score": round(score, 3),
            }
        )

    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows


def _benchmark_row(performance_report: PerformanceReport) -> list[dict[str, Any]]:
    benchmark = {
        "ctr": 0.020,
        "cpc": 2.50,
        "cpa": 70.0,
        "roas": 2.50,
        "conversion_rate": 0.035,
        "frequency": 3.0,
    }

    rows: list[dict[str, Any]] = []
    for metric, benchmark_value in benchmark.items():
        actual = float(performance_report.metrics.get(metric, 0.0))
        delta = actual - benchmark_value
        rows.append(
            {
                "metric": metric,
                "actual": round(actual, 4),
                "benchmark": round(benchmark_value, 4),
                "delta": round(delta, 4),
                "status": "above" if delta >= 0 else "below",
            }
        )
    return rows


def _build_recharts_data(
    media_plan: MediaPlan,
    performance_report: PerformanceReport,
    content_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    spend_allocation = [{"name": ch.channel, "value": round(ch.budget, 2)} for ch in media_plan.channels]

    channel_efficiency = [
        {
            "channel": ch.channel,
            "impressions": ch.projected_impressions,
            "conversions": ch.projected_conversions,
            "budget": round(ch.budget, 2),
            "cpa": round(_safe_div(ch.budget, ch.projected_conversions), 2),
        }
        for ch in media_plan.channels
    ]

    anomaly_trend = []
    for anomaly in performance_report.anomalies:
        if anomaly.timestamp is None:
            continue
        anomaly_trend.append(
            {
                "date": anomaly.timestamp.isoformat(),
                "metric": anomaly.metric,
                "value": anomaly.observed_value,
                "severity": anomaly.severity,
            }
        )

    top_assets = [
        {
            "asset_id": row["asset_id"],
            "score": row["score"],
            "platform": row["platform"],
            "conversions": row["conversions"],
        }
        for row in content_rows[:8]
    ]

    return {
        "spend_allocation_pie": spend_allocation,
        "channel_efficiency_bar": channel_efficiency,
        "anomaly_trend_line": anomaly_trend,
        "top_assets_bar": top_assets,
    }


def _best_worst_channel(media_plan: MediaPlan) -> tuple[str, str]:
    if not media_plan.channels:
        return "N/A", "N/A"

    def efficiency(channel: Any) -> float:
        if channel.budget <= 0:
            return 0.0
        return channel.projected_conversions / channel.budget

    ranked = sorted(media_plan.channels, key=efficiency, reverse=True)
    return ranked[0].channel, ranked[-1].channel


def _build_default_exec_summary(strategy: CampaignStrategy, performance_report: PerformanceReport) -> str:
    roas = performance_report.metrics.get("roas", 0.0)
    ctr = performance_report.metrics.get("ctr", 0.0)
    cpa = performance_report.metrics.get("cpa", 0.0)

    lessons = []
    if performance_report.underperforming_channels:
        lessons.append("Channel-level variance indicates stronger upside from dynamic budget reallocation.")
    if performance_report.underperforming_assets:
        lessons.append("Creative fatigue signals the need for faster asset refresh cycles.")
    if not lessons:
        lessons.append("Execution quality remained stable with no severe channel regressions.")

    return (
        "Campaign outcomes showed measurable progress against strategic objectives. "
        f"Current efficiency delivered ROAS {roas:.2f}, CTR {ctr:.2%}, and CPA {cpa:.2f}. "
        "Key achievements include multi-channel delivery consistency and actionable optimization learnings. "
        + " ".join(lessons)
    )


def _build_section(template_key: str, **kwargs: Any) -> Section:
    template = SECTION_TEMPLATES[template_key]
    return Section(
        title=template["title"],
        summary=kwargs.get("summary", template["summary"]),
        bullets=kwargs.get("bullets", []),
        table_headers=kwargs.get("table_headers", []),
        table_rows=kwargs.get("table_rows", []),
    )


async def _llm_exec_layers(
    llm: ChatOpenAI,
    strategy: CampaignStrategy,
    performance_report: PerformanceReport,
    media_plan: MediaPlan,
    max_retries: int,
) -> LLMReportEnvelope:
    payload = {
        "strategy_objectives": strategy.objectives,
        "strategy_channels": [c.channel for c in strategy.recommended_channels],
        "performance_metrics": performance_report.metrics,
        "anomalies": [a.model_dump(mode="json") for a in performance_report.anomalies[:10]],
        "media_plan": {
            "total_budget": media_plan.total_budget,
            "daily_budget": media_plan.daily_budget,
            "channels": [{"channel": c.channel, "budget": c.budget, "conversions": c.projected_conversions} for c in media_plan.channels],
        },
        "instruction": "Provide a concise executive summary, 5-7 recommendations, and 5-7 prioritized next steps.",
    }

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(payload)),
    ]

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = await llm.ainvoke(messages)
            parsed = _parse_llm_content(response.content)
            return LLMReportEnvelope.model_validate(parsed)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            logger.warning("campaign_reporter LLM attempt %s/%s failed: %s", attempt, max_retries, exc)

    raise RuntimeError(str(last_error) if last_error else "LLM report generation failed")


def export_report_json(final_report: FinalReport) -> dict[str, Any]:
    return final_report.model_dump(mode="json")


def export_report_markdown(final_report: FinalReport) -> str:
    lines: list[str] = ["# Campaign Final Report", "", "## Executive Summary", final_report.executive_summary, ""]

    for section in final_report.detailed_sections:
        lines.append(f"## {section.title}")
        lines.append(section.summary)
        lines.append("")

        for bullet in section.bullets:
            lines.append(f"- {bullet}")

        if section.table_headers and section.table_rows:
            lines.append("")
            lines.append("| " + " | ".join(section.table_headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(section.table_headers)) + " |")
            for row in section.table_rows:
                lines.append("| " + " | ".join(str(row.get(h, "")) for h in section.table_headers) + " |")
        lines.append("")

    lines.append("## Recommendations")
    for rec in final_report.recommendations:
        lines.append(f"- {rec}")
    lines.append("")

    lines.append("## Next Steps")
    for step in final_report.next_steps:
        lines.append(f"- {step}")
    lines.append("")

    return "\n".join(lines)


def export_report_pdf_bytes(final_report: FinalReport) -> bytes:
    try:
        from io import BytesIO

        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PDF export requires reportlab. Install with: pip install reportlab") from exc

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [Paragraph("Campaign Final Report", styles["Title"]), Spacer(1, 12)]

    story.append(Paragraph("Executive Summary", styles["Heading2"]))
    story.append(Paragraph(final_report.executive_summary, styles["BodyText"]))
    story.append(Spacer(1, 12))

    for section in final_report.detailed_sections:
        story.append(Paragraph(section.title, styles["Heading2"]))
        story.append(Paragraph(section.summary, styles["BodyText"]))
        story.append(Spacer(1, 6))
        for bullet in section.bullets[:8]:
            story.append(Paragraph(f"• {bullet}", styles["BodyText"]))
        story.append(Spacer(1, 10))

    story.append(Paragraph("Recommendations", styles["Heading2"]))
    for rec in final_report.recommendations[:10]:
        story.append(Paragraph(f"• {rec}", styles["BodyText"]))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Next Steps", styles["Heading2"]))
    for step in final_report.next_steps[:10]:
        story.append(Paragraph(f"• {step}", styles["BodyText"]))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


async def campaign_reporter_node(state: dict[str, Any], max_retries: int = 3, llm: ChatOpenAI | None = None) -> dict[str, Any]:
    raw_strategy = state.get("campaign_strategy")
    raw_content = state.get("content_package")
    raw_media = state.get("media_plan")
    raw_performance = state.get("performance_report")
    raw_logs = state.get("agent_logs", [])

    if raw_strategy is None:
        raise ValueError("Missing required state key: campaign_strategy")
    if raw_content is None:
        raise ValueError("Missing required state key: content_package")
    if raw_media is None:
        raise ValueError("Missing required state key: media_plan")
    if raw_performance is None:
        raise ValueError("Missing required state key: performance_report")

    strategy = raw_strategy if isinstance(raw_strategy, CampaignStrategy) else CampaignStrategy.model_validate(raw_strategy)
    content_package = raw_content if isinstance(raw_content, ContentPackage) else ContentPackage.model_validate(raw_content)
    media_plan = raw_media if isinstance(raw_media, MediaPlan) else MediaPlan.model_validate(raw_media)
    performance_report = raw_performance if isinstance(raw_performance, PerformanceReport) else PerformanceReport.model_validate(raw_performance)
    agent_logs = [log if isinstance(log, AgentLogEntry) else AgentLogEntry.model_validate(log) for log in raw_logs]

    channel_rows = _channel_performance_rows(media_plan)
    asset_rows = _asset_performance_rows(content_package)
    benchmark_rows = _benchmark_row(performance_report)

    best_assets = asset_rows[:5]
    worst_assets = list(reversed(asset_rows[-5:])) if len(asset_rows) > 5 else []

    planned_budget = sum(strategy.budget_allocation.values())
    actual_spend = float(performance_report.metrics.get("spend", media_plan.total_budget))
    spend_variance = actual_spend - planned_budget
    best_channel, worst_channel = _best_worst_channel(media_plan)

    details = [
        _build_section(
            "detailed_performance",
            bullets=[
                f"Total projected reach: {sum(c.projected_reach for c in media_plan.channels):,}",
                f"Total projected impressions: {sum(c.projected_impressions for c in media_plan.channels):,}",
                f"Optimization score: {performance_report.optimization_score:.2f}",
                f"Best performing channel: {best_channel}",
                f"Worst performing channel: {worst_channel}",
            ],
            table_headers=["channel", "budget", "budget_pct", "impressions", "reach", "clicks", "conversions", "bid_strategy"],
            table_rows=channel_rows,
        ),
        _build_section(
            "content_performance",
            bullets=[
                f"Best creative asset: {best_assets[0]['asset_id']} (score {best_assets[0]['score']})" if best_assets else "No asset performance metadata available.",
                f"Worst creative asset: {worst_assets[0]['asset_id']} (score {worst_assets[0]['score']})" if worst_assets else "Insufficient assets to identify worst performer.",
            ],
            table_headers=["asset_id", "platform", "persona", "variant", "ctr", "conversions", "cpa", "score"],
            table_rows=best_assets + worst_assets,
        ),
        _build_section(
            "budget_analysis",
            bullets=[
                f"Planned budget: {planned_budget:.2f}",
                f"Actual spend: {actual_spend:.2f}",
                f"Variance: {spend_variance:.2f}",
                f"Observed ROAS: {performance_report.metrics.get('roas', 0.0):.2f}",
                f"Observed CPA: {performance_report.metrics.get('cpa', 0.0):.2f}",
                f"Best performing channel: {best_channel}",
                f"Worst performing channel: {worst_channel}",
            ],
            table_headers=["metric", "value"],
            table_rows=[
                {"metric": "planned_budget", "value": round(planned_budget, 2)},
                {"metric": "actual_spend", "value": round(actual_spend, 2)},
                {"metric": "spend_variance", "value": round(spend_variance, 2)},
                {"metric": "roas", "value": round(performance_report.metrics.get("roas", 0.0), 4)},
                {"metric": "cpa", "value": round(performance_report.metrics.get("cpa", 0.0), 4)},
            ],
        ),
        _build_section(
            "audience_insights",
            bullets=[
                "Highest responsiveness segments should receive incremental budget in next flight.",
                "Unexpected high-intent pockets were observed in secondary persona cohorts.",
                "Low-engagement segments should be excluded or down-weighted in bid models.",
            ],
            table_headers=["signal", "details"],
            table_rows=[
                {"signal": "underperforming_channels", "details": ", ".join(performance_report.underperforming_channels) or "None flagged"},
                {"signal": "underperforming_assets", "details": ", ".join(performance_report.underperforming_assets) or "None flagged"},
            ],
        ),
        _build_section(
            "competitive_analysis",
            bullets=[
                "Benchmark comparison indicates where cost and conversion efficiency diverged.",
                "Prioritize channels that maintain benchmark-positive ROAS deltas.",
            ],
            table_headers=["metric", "actual", "benchmark", "delta", "status"],
            table_rows=benchmark_rows,
        ),
    ]

    base_recommendations = [r.action if hasattr(r, "action") else str(r) for r in performance_report.recommendations[:7]]
    base_next_steps = [
        "Reallocate next-cycle budget using channel-level ROAS and CPA deltas.",
        "Refresh bottom-quartile creatives and relaunch with controlled A/B tests.",
        "Tighten audience exclusions for low-quality cohorts.",
        "Implement weekly anomaly review and escalation cadence.",
        "Update benchmark assumptions with latest campaign learnings.",
    ]

    exec_summary = _build_default_exec_summary(strategy, performance_report)
    llm_used = False

    model = llm
    if model is None:
        try:
            model = _build_llm()
        except Exception:
            model = None

    if model is not None:
        try:
            llm_report = await _llm_exec_layers(
                llm=model,
                strategy=strategy,
                performance_report=performance_report,
                media_plan=media_plan,
                max_retries=max_retries,
            )
            exec_summary = llm_report.executive_summary
            if llm_report.recommendations:
                base_recommendations = llm_report.recommendations[:10]
            if llm_report.next_steps:
                base_next_steps = llm_report.next_steps[:10]
            llm_used = True
        except Exception as exc:
            logger.warning("campaign_reporter using deterministic fallback: %s", exc)

    if agent_logs:
        details.append(
            Section(
                title="Execution Log Summary",
                summary="Cross-agent execution telemetry and orchestration health.",
                bullets=[
                    f"Total logged actions: {len(agent_logs)}",
                    f"Average latency (ms): {int(sum((log.latency_ms or 0) for log in agent_logs) / max(len(agent_logs), 1))}",
                    ("Most recent action: " + max(agent_logs, key=lambda x: x.completed_at or x.started_at or datetime.now(UTC)).action),
                ],
                table_headers=["agent_name", "action", "status", "latency_ms"],
                table_rows=[
                    {
                        "agent_name": log.agent_name,
                        "action": log.action,
                        "status": log.status,
                        "latency_ms": log.latency_ms,
                    }
                    for log in agent_logs[:20]
                ],
            )
        )

    charts_data = _build_recharts_data(media_plan, performance_report, asset_rows)

    final_report = FinalReport(
        executive_summary=exec_summary,
        detailed_sections=details,
        charts_data=charts_data,
        recommendations=base_recommendations,
        next_steps=base_next_steps,
    )

    markdown = export_report_markdown(final_report)
    report_json = export_report_json(final_report)

    pdf_available = True
    pdf_bytes: bytes | None = None
    pdf_error: str | None = None
    try:
        pdf_bytes = export_report_pdf_bytes(final_report)
    except RuntimeError as exc:
        pdf_available = False
        pdf_error = str(exc)

    return {
        "agent_name": AGENT_NAME,
        "final_report": final_report.model_dump(mode="json"),
        "report_exports": {
            "json": report_json,
            "markdown": markdown,
            "pdf": {
                "available": pdf_available,
                "bytes": pdf_bytes,
                "error": pdf_error,
            },
        },
        "report_metadata": {
            "sections": len(final_report.detailed_sections),
            "llm_used": llm_used,
        },
    }
