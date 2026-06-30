import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.media_buyer import MediaPlan, media_buyer_node


def _strategy_payload() -> dict:
    return {
        "objectives": ["Increase conversion volume by 20% within 60 days"],
        "target_audiences": [
            {
                "name": "Growth Manager",
                "segment": "B2B SaaS",
                "demographics": ["Age 28-45", "North America"],
                "pain_points": ["High CAC", "Inconsistent lead quality"],
                "motivations": ["Pipeline growth", "Efficient budget use"],
            }
        ],
        "key_messages": ["Scale conversion with measurable ROI"],
        "recommended_channels": [
            {
                "channel": "Google Ads",
                "budget_percentage": 50,
                "rationale": "High intent",
                "execution_notes": ["Intent keywords"],
            }
        ],
        "timeline": [
            {
                "day": 1,
                "title": "Kickoff",
                "description": "Launch campaigns",
                "success_criteria": "Tracking active",
            },
            {
                "day": 60,
                "title": "Final review",
                "description": "Consolidate winners",
                "success_criteria": "CPA target achieved",
            },
        ],
        "budget_allocation": {"Google Ads": 30000},
        "competitive_differentiation": ["Faster implementation"],
        "confidence_score": 0.81,
    }


def _content_package_single_channel() -> dict:
    return {
        "assets": [
            {
                "asset_id": "ad-1",
                "asset_type": "ad_copy",
                "platform": "google_ads",
                "persona_name": "Growth Manager",
                "title": "Reduce CAC in 30 Days",
                "body": "Run high-intent campaigns with stronger conversion rates.",
                "cta": "Book Demo",
                "variant": "A",
                "day": None,
                "utm_parameters": {
                    "source": "google",
                    "medium": "cpc",
                    "campaign": "q3_conversion",
                    "content": "ad_1",
                    "term": "campaign automation",
                },
                "ab_test": {
                    "variant_a": "ROI-first",
                    "variant_b": "Pain-first",
                    "hypothesis": "ROI framing improves CVR",
                },
                "metadata": {},
            }
        ]
    }


def _content_package_multi_channel() -> dict:
    base = _content_package_single_channel()["assets"]
    return {
        "assets": base
        + [
            {**base[0], "asset_id": "ad-2", "platform": "meta_ads"},
            {**base[0], "asset_id": "ad-3", "platform": "linkedin_ads"},
        ]
    }


def _student_strategy_payload() -> dict:
    return {
        "objectives": ["Increase awareness among students"],
        "target_audiences": [
            {
                "name": "Student Persona",
                "segment": "Students",
                "demographics": ["University students"],
                "pain_points": ["Budget sensitivity"],
                "motivations": ["Career growth"],
            }
        ],
        "key_messages": ["Affordable and practical"],
        "recommended_channels": [],
        "timeline": [
            {"day": 1, "title": "Launch", "description": "Start", "success_criteria": "Live"}
        ],
        "budget_allocation": {},
        "competitive_differentiation": ["Student friendly"],
        "confidence_score": 0.75,
    }


@pytest.mark.asyncio
async def test_media_buyer_zero_budget_returns_empty_plan():
    result = await media_buyer_node(
        state={
            "campaign_strategy": _strategy_payload(),
            "content_package": _content_package_multi_channel(),
            "total_budget": 0,
        }
    )

    assert result["agent_name"] == "media_buyer"
    assert result["media_plan_valid"] is True
    assert result["media_plan"]["total_budget"] == 0
    assert result["media_plan"]["daily_budget"] == 0
    assert result["media_plan"]["channels"] == []


@pytest.mark.asyncio
async def test_media_buyer_single_channel_allocates_all_budget():
    result = await media_buyer_node(
        state={
            "campaign_strategy": _strategy_payload(),
            "content_package": _content_package_single_channel(),
            "total_budget": 1200,
        }
    )

    assert result["media_plan_valid"] is True
    channels = result["media_plan"]["channels"]
    assert len(channels) == 1
    assert channels[0]["channel"] == "google_ads"
    assert channels[0]["budget"] == pytest.approx(1200)
    assert channels[0]["budget_percentage"] == pytest.approx(100)
    assert channels[0]["projected_impressions"] > 0


def test_media_plan_budget_validator_rejects_mismatch():
    with pytest.raises(ValueError):
        MediaPlan.model_validate(
            {
                "channels": [
                    {
                        "channel": "google_ads",
                        "budget": 400,
                        "budget_percentage": 40,
                        "bid_strategy": "target CPA",
                        "targeting": {
                            "demographics": [],
                            "interests": [],
                            "behaviors": [],
                            "lookalike_audiences": [],
                        },
                        "projected_reach": 1000,
                        "projected_impressions": 1500,
                        "projected_clicks": 20,
                        "projected_conversions": 2,
                        "rationale": "test",
                    }
                ],
                "total_budget": 1000,
                "daily_budget": 16.67,
                "bid_strategy": "target CPA",
                "targeting": {
                    "demographics": [],
                    "interests": [],
                    "behaviors": [],
                    "lookalike_audiences": [],
                },
                "flight_dates": {
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-30",
                    "dayparting_recommendations": [],
                },
            }
        )


@pytest.mark.asyncio
async def test_media_buyer_student_budget_recommends_social_video_mix():
    result = await media_buyer_node(
        state={
            "campaign_strategy": _student_strategy_payload(),
            "content_package": _content_package_multi_channel(),
            "total_budget": 1000,
        }
    )

    assert result["media_plan_valid"] is True
    channels = {item["channel"]: item for item in result["media_plan"]["channels"]}
    assert set(channels.keys()) == {"instagram", "tiktok", "youtube"}
    assert channels["instagram"]["budget_percentage"] == pytest.approx(40, abs=0.01)
    assert channels["tiktok"]["budget_percentage"] == pytest.approx(35, abs=0.01)
    assert channels["youtube"]["budget_percentage"] == pytest.approx(25, abs=0.01)


@pytest.mark.asyncio
async def test_media_buyer_high_budget_uses_omnichannel_mix():
    result = await media_buyer_node(
        state={
            "campaign_strategy": _strategy_payload(),
            "content_package": _content_package_multi_channel(),
            "total_budget": 500000,
        }
    )

    channels = {item["channel"] for item in result["media_plan"]["channels"]}
    assert "google_ads" in channels
    assert "linkedin_ads" in channels
    assert "facebook" in channels
    assert "display" in channels
    assert "youtube" in channels


@pytest.mark.asyncio
async def test_media_buyer_negative_budget_raises_validation_error():
    with pytest.raises(Exception):
        await media_buyer_node(
            state={
                "campaign_strategy": _strategy_payload(),
                "content_package": _content_package_multi_channel(),
                "total_budget": -500,
            }
        )
