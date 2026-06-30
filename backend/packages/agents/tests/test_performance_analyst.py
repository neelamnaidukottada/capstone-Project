import json
import pathlib
import sys
from datetime import date, timedelta

import pytest
from langchain_core.messages import AIMessage

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.performance_analyst import (  # noqa: E402
    CampaignExecutionData,
    TimeSeriesDataPoint,
    calculate_kpis,
    detect_anomalies_iqr,
    detect_anomalies_zscore,
    performance_analyst_node,
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


def _sample_execution_data() -> dict:
    base_day = date(2026, 6, 1)
    points = []
    for i in range(10):
        day = base_day + timedelta(days=i)
        points.append(
            {
                "timestamp": day.isoformat(),
                "channel": "google_ads" if i % 2 == 0 else "meta_ads",
                "asset_id": f"asset_{i % 3}",
                "impressions": 12000 + (i * 300),
                "clicks": 240 + (i * 6),
                "conversions": 16 + (i % 4),
                "spend": 420 + (i * 12),
                "revenue": 1450 + (i * 40),
                "unique_reach": 5200 + (i * 120),
            }
        )

    # Inject a clear outlier day for anomaly tests.
    points[7]["spend"] = 3200
    points[7]["clicks"] = 90
    points[7]["conversions"] = 2

    totals = {
        "impressions": sum(p["impressions"] for p in points),
        "clicks": sum(p["clicks"] for p in points),
        "conversions": sum(p["conversions"] for p in points),
        "spend": sum(p["spend"] for p in points),
        "revenue": sum(p["revenue"] for p in points),
        "unique_reach": sum(p["unique_reach"] for p in points),
    }

    return {
        **totals,
        "objective": "conversion",
        "campaign_duration_days": 30,
        "target_metrics": {
            "ctr": 0.022,
            "cpa": 55,
            "roas": 2.8,
            "conversion_rate": 0.04,
        },
        "time_series_data": points,
    }


@pytest.mark.asyncio
async def test_performance_analyst_node_outputs_report_and_dashboard():
    llm_response = {
        "recommendations": [
            {
                "category": "budget_reallocation",
                "action": "Shift 20% spend from weak ad sets to top-converting keywords.",
                "rationale": "Large CPA variance across channels indicates inefficient budget concentration.",
                "expected_impact": "Improve ROAS by 10-15%",
                "priority": "high",
            },
            {
                "category": "creative_refresh",
                "action": "Deploy 3 new creatives per channel targeting fatigued audiences.",
                "rationale": "CTR trend signals creative fatigue in week 2.",
                "expected_impact": "Increase CTR and lower CPC",
                "priority": "medium",
            },
        ]
    }

    llm = FakeLLM([json.dumps(llm_response)])
    result = await performance_analyst_node(
        state={"campaign_execution_data": _sample_execution_data()},
        llm=llm,
    )

    assert result["agent_name"] == "performance_analyst"
    assert "performance_report" in result
    assert "dashboard_data" in result

    report = result["performance_report"]
    assert report["metrics"]["ctr"] > 0
    assert report["metrics"]["cpc"] > 0
    assert report["metrics"]["conversion_rate"] > 0
    assert 0 <= report["optimization_score"] <= 1
    assert len(report["recommendations"]) >= 2

    dashboard = result["dashboard_data"]
    assert "kpi_cards" in dashboard
    assert "channel_table" in dashboard
    assert isinstance(dashboard["channel_table"], list)


def test_zero_spend_kpi_safety():
    data = CampaignExecutionData(
        impressions=10000,
        clicks=0,
        conversions=0,
        spend=0,
        revenue=0,
        unique_reach=5000,
        objective="awareness",
        campaign_duration_days=14,
        target_metrics={},
        time_series_data=[],
    )

    metrics = calculate_kpis(data)
    assert metrics["cpc"] == 0
    assert metrics["cpa"] == 0
    assert metrics["roas"] == 0
    assert metrics["conversion_rate"] == 0


def test_anomaly_detectors_identify_outliers():
    # Direct pure-python detector checks.
    values = [1.0, 1.1, 0.9, 1.05, 1.02, 7.0]
    z_outliers = detect_anomalies_zscore(values, metric="cpa", threshold=2.0)
    iqr_outliers = detect_anomalies_iqr(values)

    assert len(z_outliers) >= 1
    assert len(iqr_outliers) >= 1


def test_time_series_model_validation():
    point = TimeSeriesDataPoint(
        timestamp=date(2026, 6, 1),
        channel="google_ads",
        asset_id="asset_1",
        impressions=1000,
        clicks=40,
        conversions=4,
        spend=120,
        revenue=420,
        unique_reach=700,
    )
    assert point.channel == "google_ads"
    assert point.impressions == 1000


@pytest.mark.asyncio
async def test_performance_analyst_poor_campaign_actions_present():
    data = {
        "impressions": 50000,
        "clicks": 250,
        "conversions": 2,
        "spend": 5000,
        "revenue": 800,
        "unique_reach": 20000,
        "objective": "conversion",
        "campaign_duration_days": 30,
        "target_metrics": {},
        "time_series_data": [
            {
                "timestamp": "2026-06-01",
                "channel": "google_ads",
                "asset_id": "asset_1",
                "impressions": 50000,
                "clicks": 250,
                "conversions": 2,
                "spend": 5000,
                "revenue": 800,
                "unique_reach": 20000,
            }
        ],
    }

    result = await performance_analyst_node(state={"campaign_execution_data": data})
    actions = " ".join(rec["action"].lower() for rec in result["performance_report"]["recommendations"])

    assert "headline" in actions
    assert "audience" in actions
    assert "reduce cpc" in actions or "cpc" in actions
    assert "pause" in actions and "low-performing" in actions


@pytest.mark.asyncio
async def test_performance_analyst_excellent_campaign_scales():
    data = {
        "impressions": 100000,
        "clicks": 8000,
        "conversions": 900,
        "spend": 10000,
        "revenue": 70000,
        "unique_reach": 40000,
        "objective": "conversion",
        "campaign_duration_days": 30,
        "target_metrics": {},
        "time_series_data": [],
    }

    result = await performance_analyst_node(state={"campaign_execution_data": data})
    actions = " ".join(rec["action"].lower() for rec in result["performance_report"]["recommendations"])

    assert "scale budget" in actions or "scale" in actions
    assert "duplicate winning ads" in actions or "duplicate" in actions
