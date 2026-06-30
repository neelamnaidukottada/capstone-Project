"""Performance Analyst LangGraph node.

Analyzes campaign execution data, detects anomalies, compares against benchmarks,
and produces optimization recommendations.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date
from statistics import mean
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError, model_validator

logger = logging.getLogger(__name__)

AGENT_NAME = "performance_analyst"


class TimeSeriesDataPoint(BaseModel):
    timestamp: date
    channel: str
    asset_id: str | None = None
    impressions: int = Field(..., ge=0)
    clicks: int = Field(..., ge=0)
    conversions: int = Field(..., ge=0)
    spend: float = Field(..., ge=0)
    revenue: float = Field(default=0, ge=0)
    unique_reach: int = Field(default=0, ge=0)


class CampaignExecutionData(BaseModel):
    impressions: int = Field(..., ge=0)
    clicks: int = Field(..., ge=0)
    conversions: int = Field(..., ge=0)
    spend: float = Field(..., ge=0)
    revenue: float = Field(default=0, ge=0)
    unique_reach: int = Field(default=0, ge=0)
    objective: str = Field(default="conversion")
    campaign_duration_days: int = Field(default=30, ge=1)
    target_metrics: dict[str, float] = Field(default_factory=dict)
    time_series_data: list[TimeSeriesDataPoint] = Field(default_factory=list)


class Anomaly(BaseModel):
    metric: str
    method: str
    severity: str
    observed_value: float
    expected_value: float
    description: str
    channel: str | None = None
    asset_id: str | None = None
    timestamp: date | None = None


class Recommendation(BaseModel):
    category: str
    action: str
    rationale: str
    expected_impact: str
    priority: str = Field(default="medium")


class PerformanceReport(BaseModel):
    metrics: dict[str, float]
    anomalies: list[Anomaly]
    recommendations: list[Recommendation]
    optimization_score: float = Field(..., ge=0, le=1)
    projected_end_of_campaign: dict[str, float] = Field(default_factory=dict)
    underperforming_channels: list[str] = Field(default_factory=list)
    underperforming_assets: list[str] = Field(default_factory=list)


class LLMRecommendationBatch(BaseModel):
    recommendations: list[Recommendation] = Field(default_factory=list)


SYSTEM_PROMPT = """You are a senior performance marketing analyst and data scientist.
You specialize in paid media optimization, causal diagnosis, and budget efficiency.

Responsibilities:
- Interpret campaign performance data rigorously.
- Use KPI context (CTR, CPC, CPA, ROAS, CVR, frequency).
- Generate practical actions for budget shifts, audience refinements, creative refreshes, and bid strategy changes.
- Keep recommendations concrete and testable.

Output only strict JSON matching schema.
"""


BENCHMARKS: dict[str, dict[str, float]] = {
    "awareness": {
        "ctr": 0.012,
        "cpc": 2.00,
        "cpa": 120.0,
        "roas": 1.2,
        "conversion_rate": 0.018,
        "frequency": 2.8,
    },
    "conversion": {
        "ctr": 0.020,
        "cpc": 1.80,
        "cpa": 70.0,
        "roas": 2.5,
        "conversion_rate": 0.035,
        "frequency": 3.5,
    },
    "retention": {
        "ctr": 0.017,
        "cpc": 1.60,
        "cpa": 55.0,
        "roas": 3.2,
        "conversion_rate": 0.042,
        "frequency": 4.2,
    },
}


def _safe_div(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return a / b


def calculate_kpis(data: CampaignExecutionData) -> dict[str, float]:
    ctr = _safe_div(data.clicks, data.impressions)
    cpc = _safe_div(data.spend, data.clicks)
    cpa = _safe_div(data.spend, data.conversions)
    roas = _safe_div(data.revenue, data.spend)
    conversion_rate = _safe_div(data.conversions, data.clicks)
    frequency = _safe_div(data.impressions, data.unique_reach) if data.unique_reach > 0 else 0.0

    return {
        "impressions": float(data.impressions),
        "clicks": float(data.clicks),
        "conversions": float(data.conversions),
        "spend": float(data.spend),
        "revenue": float(data.revenue),
        "ctr": ctr,
        "cpc": cpc,
        "cpa": cpa,
        "roas": roas,
        "conversion_rate": conversion_rate,
        "frequency": frequency,
    }


def _std_dev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    variance = sum((v - m) ** 2 for v in values) / len(values)
    return variance ** 0.5


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]

    index = (len(sorted_values) - 1) * p
    lo = int(index)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = index - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def detect_anomalies_zscore(
    values: list[float],
    metric: str,
    threshold: float = 2.5,
) -> list[tuple[int, float, float, float]]:
    """Return tuples: (index, value, mean, z_score) for outliers."""
    if len(values) < 3:
        return []

    m = mean(values)
    sd = _std_dev(values)
    if sd == 0:
        return []

    outliers: list[tuple[int, float, float, float]] = []
    for i, value in enumerate(values):
        z = (value - m) / sd
        if abs(z) >= threshold:
            outliers.append((i, value, m, z))
    return outliers


def detect_anomalies_iqr(
    values: list[float],
    multiplier: float = 1.5,
) -> list[tuple[int, float, float, float]]:
    """Return tuples: (index, value, lower_bound, upper_bound) for IQR outliers."""
    if len(values) < 4:
        return []

    sorted_values = sorted(values)
    q1 = _percentile(sorted_values, 0.25)
    q3 = _percentile(sorted_values, 0.75)
    iqr = q3 - q1
    lower = q1 - (multiplier * iqr)
    upper = q3 + (multiplier * iqr)

    outliers: list[tuple[int, float, float, float]] = []
    for i, value in enumerate(values):
        if value < lower or value > upper:
            outliers.append((i, value, lower, upper))
    return outliers


def _aggregate_by_channel(data: CampaignExecutionData) -> dict[str, dict[str, float]]:
    agg: dict[str, dict[str, float]] = defaultdict(lambda: {
        "impressions": 0.0,
        "clicks": 0.0,
        "conversions": 0.0,
        "spend": 0.0,
        "revenue": 0.0,
    })

    for point in data.time_series_data:
        row = agg[point.channel]
        row["impressions"] += point.impressions
        row["clicks"] += point.clicks
        row["conversions"] += point.conversions
        row["spend"] += point.spend
        row["revenue"] += point.revenue

    return dict(agg)


def _collect_statistical_anomalies(data: CampaignExecutionData) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    if not data.time_series_data:
        return anomalies

    ctr_series = [_safe_div(p.clicks, p.impressions) for p in data.time_series_data]
    cvr_series = [_safe_div(p.conversions, p.clicks) for p in data.time_series_data]
    cpa_series = [_safe_div(p.spend, p.conversions) if p.conversions > 0 else p.spend for p in data.time_series_data]
    spend_series = [p.spend for p in data.time_series_data]

    for metric, series in [
        ("ctr", ctr_series),
        ("conversion_rate", cvr_series),
        ("cpa", cpa_series),
        ("spend", spend_series),
    ]:
        z_outliers = detect_anomalies_zscore(series, metric)
        for idx, value, expected, z in z_outliers:
            point = data.time_series_data[idx]
            severity = "high" if abs(z) >= 3.5 else "medium"
            anomalies.append(
                Anomaly(
                    metric=metric,
                    method="z-score",
                    severity=severity,
                    observed_value=float(value),
                    expected_value=float(expected),
                    description=f"{metric} outlier detected (z={z:.2f}).",
                    channel=point.channel,
                    asset_id=point.asset_id,
                    timestamp=point.timestamp,
                )
            )

        iqr_outliers = detect_anomalies_iqr(series)
        for idx, value, lower, upper in iqr_outliers:
            point = data.time_series_data[idx]
            anomalies.append(
                Anomaly(
                    metric=metric,
                    method="IQR",
                    severity="medium",
                    observed_value=float(value),
                    expected_value=float((lower + upper) / 2),
                    description=f"{metric} outside IQR bounds [{lower:.4f}, {upper:.4f}].",
                    channel=point.channel,
                    asset_id=point.asset_id,
                    timestamp=point.timestamp,
                )
            )

    # Deduplicate near-identical anomalies.
    unique: dict[tuple[str, str, str | None, date | None], Anomaly] = {}
    for an in anomalies:
        key = (an.metric, an.method, an.channel, an.timestamp)
        unique[key] = an
    return list(unique.values())


def _benchmark_compare(
    metrics: dict[str, float],
    objective: str,
    target_metrics: dict[str, float],
) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    benchmark = BENCHMARKS.get(objective, BENCHMARKS["conversion"])

    for metric, bench_value in benchmark.items():
        actual = metrics.get(metric, 0.0)
        if metric in {"ctr", "roas", "conversion_rate"}:
            if actual < bench_value * 0.8:
                anomalies.append(
                    Anomaly(
                        metric=metric,
                        method="benchmark",
                        severity="high",
                        observed_value=actual,
                        expected_value=bench_value,
                        description=f"{metric} is materially below benchmark.",
                    )
                )
        else:
            if actual > bench_value * 1.25:
                anomalies.append(
                    Anomaly(
                        metric=metric,
                        method="benchmark",
                        severity="high",
                        observed_value=actual,
                        expected_value=bench_value,
                        description=f"{metric} is materially above benchmark (cost pressure).",
                    )
                )

    for metric, target in target_metrics.items():
        actual = metrics.get(metric)
        if actual is None:
            continue
        # Infer direction from common metric semantics.
        higher_better = metric in {"ctr", "roas", "conversion_rate", "conversions"}
        miss = actual < target if higher_better else actual > target
        if miss:
            anomalies.append(
                Anomaly(
                    metric=metric,
                    method="goal_gap",
                    severity="medium",
                    observed_value=float(actual),
                    expected_value=float(target),
                    description=f"{metric} is off target goal.",
                )
            )

    return anomalies


def _underperformers(
    data: CampaignExecutionData,
    objective: str,
) -> tuple[list[str], list[str]]:
    benchmark = BENCHMARKS.get(objective, BENCHMARKS["conversion"])
    by_channel = _aggregate_by_channel(data)

    under_channels: list[str] = []
    for channel, row in by_channel.items():
        ctr = _safe_div(row["clicks"], row["impressions"])
        cpa = _safe_div(row["spend"], row["conversions"]) if row["conversions"] > 0 else row["spend"]
        if ctr < benchmark["ctr"] * 0.75 or cpa > benchmark["cpa"] * 1.35:
            under_channels.append(channel)

    asset_map: dict[str, dict[str, float]] = defaultdict(lambda: {
        "impressions": 0.0,
        "clicks": 0.0,
        "conversions": 0.0,
        "spend": 0.0,
    })
    for point in data.time_series_data:
        if not point.asset_id:
            continue
        row = asset_map[point.asset_id]
        row["impressions"] += point.impressions
        row["clicks"] += point.clicks
        row["conversions"] += point.conversions
        row["spend"] += point.spend

    under_assets: list[str] = []
    for asset_id, row in asset_map.items():
        ctr = _safe_div(row["clicks"], row["impressions"])
        cpa = _safe_div(row["spend"], row["conversions"]) if row["conversions"] > 0 else row["spend"]
        if ctr < benchmark["ctr"] * 0.7 or cpa > benchmark["cpa"] * 1.5:
            under_assets.append(asset_id)

    return under_channels, under_assets


def _predict_end_of_campaign(
    data: CampaignExecutionData,
    metrics: dict[str, float],
) -> dict[str, float]:
    observed_days = len({p.timestamp for p in data.time_series_data}) or 1
    remaining_days = max(data.campaign_duration_days - observed_days, 0)

    daily_impressions = _safe_div(data.impressions, observed_days)
    daily_clicks = _safe_div(data.clicks, observed_days)
    daily_conversions = _safe_div(data.conversions, observed_days)
    daily_spend = _safe_div(data.spend, observed_days)
    daily_revenue = _safe_div(data.revenue, observed_days)

    projected_impressions = data.impressions + int(daily_impressions * remaining_days)
    projected_clicks = data.clicks + int(daily_clicks * remaining_days)
    projected_conversions = data.conversions + int(daily_conversions * remaining_days)
    projected_spend = data.spend + (daily_spend * remaining_days)
    projected_revenue = data.revenue + (daily_revenue * remaining_days)

    projected_roas = _safe_div(projected_revenue, projected_spend)

    return {
        "projected_impressions": float(projected_impressions),
        "projected_clicks": float(projected_clicks),
        "projected_conversions": float(projected_conversions),
        "projected_spend": float(round(projected_spend, 2)),
        "projected_revenue": float(round(projected_revenue, 2)),
        "projected_roas": float(round(projected_roas, 4)),
        "current_roas": float(round(metrics.get("roas", 0.0), 4)),
    }


def _rule_based_recommendations(
    metrics: dict[str, float],
    anomalies: list[Anomaly],
    under_channels: list[str],
    under_assets: list[str],
    objective: str,
) -> list[Recommendation]:
    recs: list[Recommendation] = []
    benchmark = BENCHMARKS.get(objective, BENCHMARKS["conversion"])

    ctr_value = metrics.get("ctr", 0.0)
    roas_value = metrics.get("roas", 0.0)
    cpc_value = metrics.get("cpc", 0.0)

    # Excellent campaign handling: focus on scaling, avoid unnecessary warning-heavy guidance.
    if ctr_value >= 0.06 and roas_value >= 5.0:
        return [
            Recommendation(
                category="budget_scaling",
                action="Scale budget incrementally (15-25%) on top-performing channels.",
                rationale="CTR and ROAS significantly exceed benchmark, indicating profitable headroom.",
                expected_impact="Increase conversion volume while maintaining strong efficiency.",
                priority="high",
            ),
            Recommendation(
                category="creative_scaling",
                action="Duplicate winning ads into adjacent audience segments and geos.",
                rationale="Top creatives are validated and can be extended to similar audiences.",
                expected_impact="Accelerate growth with lower testing risk.",
                priority="high",
            ),
        ]

    # Budget reallocation
    if under_channels:
        recs.append(
            Recommendation(
                category="budget_reallocation",
                action=(
                    f"Shift 15-25% budget away from underperforming channels: {', '.join(under_channels[:3])}. Pause low-performing ads in those channels."
                ),
                rationale="These channels are below benchmark efficiency versus campaign objective.",
                expected_impact="Improve blended CPA and ROAS within 7 days.",
                priority="high",
            )
        )

    # Audience refinements
    if metrics.get("conversion_rate", 0.0) < benchmark["conversion_rate"]:
        recs.append(
            Recommendation(
                category="audience_refinement",
                action="Change audience targeting by tightening high-intent segments and excluding low-quality cohorts.",
                rationale="Conversion rate trails benchmark; audience quality likely diluted.",
                expected_impact="Increase CVR by 10-20% and reduce wasted spend.",
                priority="high",
            )
        )

    # Creative refresh
    if under_assets or any(a.metric == "ctr" and a.severity in {"high", "medium"} for a in anomalies):
        recs.append(
            Recommendation(
                category="creative_refresh",
                action=(
                    "Improve headline and hook variants; rotate fresh creatives for top audiences; pause weak assets"
                    + (f" ({', '.join(under_assets[:4])})" if under_assets else "")
                    + "."
                ),
                rationale="CTR deterioration and asset-level underperformance signal creative fatigue.",
                expected_impact="Recover CTR and lower CPC in 3-5 days.",
                priority="medium",
            )
        )

    # Bid adjustments
    if metrics.get("cpa", 0.0) > benchmark["cpa"] or cpc_value > benchmark["cpc"]:
        recs.append(
            Recommendation(
                category="bid_adjustment",
                action="Lower bids on low-intent placements, reduce CPC with tighter keyword and placement controls, and increase bids on high-converting cohorts.",
                rationale="CPA exceeds benchmark; bid pressure should be redistributed.",
                expected_impact="Reduce CPA by 8-15% without reducing conversion volume.",
                priority="high",
            )
        )

    if not recs:
        recs.append(
            Recommendation(
                category="monitoring",
                action="Maintain current allocation and continue weekly optimization checks.",
                rationale="Performance is within expected benchmark ranges.",
                expected_impact="Sustain stable efficiency and volume.",
                priority="low",
            )
        )

    return recs


def _json_schema_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "performance_recommendations",
            "schema": LLMRecommendationBatch.model_json_schema(),
            "strict": True,
        },
    }


def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o",
        temperature=0.2,
        model_kwargs={"response_format": _json_schema_response_format()},
    )


def _parse_llm_content(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        return json.loads(content)
    if isinstance(content, list):
        joined = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return json.loads(joined)
    raise ValueError("Unsupported LLM content format")


async def _generate_llm_recommendations(
    llm: ChatOpenAI,
    execution_data: CampaignExecutionData,
    metrics: dict[str, float],
    anomalies: list[Anomaly],
    max_retries: int,
) -> list[Recommendation]:
    payload = {
        "objective": execution_data.objective,
        "metrics": metrics,
        "anomalies": [a.model_dump(mode="json") for a in anomalies][:25],
        "target_metrics": execution_data.target_metrics,
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
            result = LLMRecommendationBatch.model_validate(parsed)
            return result.recommendations
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            logger.warning(
                "performance_analyst LLM recommendations failed attempt %s/%s: %s",
                attempt,
                max_retries,
                exc,
            )
            if attempt == max_retries:
                break
    raise RuntimeError(str(last_error) if last_error else "LLM recommendation generation failed")


def compute_optimization_score(
    metrics: dict[str, float],
    anomalies: list[Anomaly],
    objective: str,
) -> float:
    benchmark = BENCHMARKS.get(objective, BENCHMARKS["conversion"])

    attainment = []
    attainment.append(min(_safe_div(metrics.get("ctr", 0), benchmark["ctr"]), 1.5))
    attainment.append(min(_safe_div(metrics.get("conversion_rate", 0), benchmark["conversion_rate"]), 1.5))
    attainment.append(min(_safe_div(metrics.get("roas", 0), benchmark["roas"]), 1.5))
    attainment.append(min(_safe_div(benchmark["cpa"], max(metrics.get("cpa", benchmark["cpa"]), 0.0001)), 1.5))

    base_score = mean(attainment) / 1.5  # normalize roughly to 0..1

    anomaly_penalty = min(len(anomalies) * 0.04, 0.35)
    severe_penalty = 0.08 * sum(1 for a in anomalies if a.severity == "high")

    score = max(0.0, min(1.0, base_score - anomaly_penalty - severe_penalty))
    return round(score, 4)


def format_realtime_dashboard_data(
    report: PerformanceReport,
    execution_data: CampaignExecutionData,
) -> dict[str, Any]:
    by_channel = _aggregate_by_channel(execution_data)

    channel_rows = []
    for channel, row in by_channel.items():
        ctr = _safe_div(row["clicks"], row["impressions"])
        cpa = _safe_div(row["spend"], row["conversions"]) if row["conversions"] > 0 else row["spend"]
        roas = _safe_div(row["revenue"], row["spend"]) if row["spend"] > 0 else 0.0
        channel_rows.append(
            {
                "channel": channel,
                "impressions": int(row["impressions"]),
                "clicks": int(row["clicks"]),
                "conversions": int(row["conversions"]),
                "spend": round(row["spend"], 2),
                "ctr": round(ctr, 4),
                "cpa": round(cpa, 2),
                "roas": round(roas, 2),
            }
        )

    return {
        "kpi_cards": {
            "ctr": round(report.metrics.get("ctr", 0.0), 4),
            "cpc": round(report.metrics.get("cpc", 0.0), 2),
            "cpa": round(report.metrics.get("cpa", 0.0), 2),
            "roas": round(report.metrics.get("roas", 0.0), 2),
            "conversion_rate": round(report.metrics.get("conversion_rate", 0.0), 4),
            "frequency": round(report.metrics.get("frequency", 0.0), 2),
            "optimization_score": report.optimization_score,
        },
        "anomaly_alerts": [a.model_dump(mode="json") for a in report.anomalies[:10]],
        "recommendations": [r.model_dump() for r in report.recommendations[:8]],
        "underperforming_channels": report.underperforming_channels,
        "underperforming_assets": report.underperforming_assets,
        "channel_table": channel_rows,
        "projection": report.projected_end_of_campaign,
    }


async def performance_analyst_node(
    state: dict[str, Any],
    max_retries: int = 3,
    llm: ChatOpenAI | None = None,
) -> dict[str, Any]:
    """LangGraph node for performance analytics and optimization guidance."""
    raw = state.get("campaign_execution_data")
    if raw is None:
        raise ValueError("Missing required state key: campaign_execution_data")

    data = raw if isinstance(raw, CampaignExecutionData) else CampaignExecutionData.model_validate(raw)

    metrics = calculate_kpis(data)
    statistical_anomalies = _collect_statistical_anomalies(data)
    benchmark_anomalies = _benchmark_compare(metrics, data.objective, data.target_metrics)

    merged_anomalies = statistical_anomalies + benchmark_anomalies

    under_channels, under_assets = _underperformers(data, data.objective)

    recommendations = _rule_based_recommendations(
        metrics=metrics,
        anomalies=merged_anomalies,
        under_channels=under_channels,
        under_assets=under_assets,
        objective=data.objective,
    )

    llm_recommendations: list[Recommendation] = []
    model = llm
    if model is None:
        try:
            model = _build_llm()
        except Exception:
            model = None

    if model is not None:
        try:
            llm_recommendations = await _generate_llm_recommendations(
                llm=model,
                execution_data=data,
                metrics=metrics,
                anomalies=merged_anomalies,
                max_retries=max_retries,
            )
        except Exception as exc:
            logger.warning("LLM recommendation fallback to rule-based only: %s", exc)

    # Keep deterministic rule-based recommendations first, then add up to 3 LLM extras.
    merged_recommendations = recommendations + llm_recommendations[:3]

    projected = _predict_end_of_campaign(data, metrics)

    optimization_score = compute_optimization_score(
        metrics=metrics,
        anomalies=merged_anomalies,
        objective=data.objective,
    )

    report = PerformanceReport(
        metrics=metrics,
        anomalies=merged_anomalies,
        recommendations=merged_recommendations,
        optimization_score=optimization_score,
        projected_end_of_campaign=projected,
        underperforming_channels=under_channels,
        underperforming_assets=under_assets,
    )

    dashboard = format_realtime_dashboard_data(report, data)

    return {
        "agent_name": AGENT_NAME,
        "performance_report": report.model_dump(mode="json"),
        "dashboard_data": dashboard,
    }
