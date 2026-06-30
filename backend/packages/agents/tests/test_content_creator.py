import json
import pathlib
import sys

import pytest
from langchain_core.messages import AIMessage

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.content_creator import BrandGuidelines, content_creator_node, validate_content_quality
from src.planner import CampaignStrategy


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
        "objectives": ["Increase leads by 25% in 90 days"],
        "target_audiences": [
            {
                "name": "Ops Leader",
                "segment": "Operations",
                "demographics": ["Age 30-50"],
                "pain_points": ["Manual workflow"],
                "motivations": ["Efficiency"],
            },
            {
                "name": "Growth Manager",
                "segment": "Marketing",
                "demographics": ["Age 28-45"],
                "pain_points": ["High CAC"],
                "motivations": ["Pipeline growth"],
            },
        ],
        "key_messages": ["Automate campaign execution"],
        "recommended_channels": [
            {
                "channel": "Google Ads",
                "budget_percentage": 40,
                "rationale": "High intent",
                "execution_notes": ["Keyword clusters"],
            }
        ],
        "timeline": [
            {
                "day": 1,
                "title": "Launch",
                "description": "Go live",
                "success_criteria": "Tracking on",
            }
        ],
        "budget_allocation": {"Google Ads": 40000},
        "competitive_differentiation": ["Faster time to value"],
        "confidence_score": 0.84,
    }


def _guidelines_payload() -> dict:
    return {
        "tone": "confident",
        "voice": "expert and practical",
        "prohibited_words": ["guaranteed"],
        "brand_colors": ["#0047AB", "#00A3A3"],
    }


def _build_batch(asset_type: str, platform: str, count: int, start_idx: int, dayed: bool = False):
    assets = []
    for i in range(count):
        assets.append(
            {
                "asset_id": f"{asset_type}-{start_idx + i}",
                "asset_type": asset_type,
                "platform": platform,
                "persona_name": "Ops Leader" if i % 2 == 0 else "Growth Manager",
                "title": "Drive More Qualified Pipeline",
                "body": "Launch data-driven campaigns that convert faster.",
                "cta": "Book a demo",
                "variant": "A" if i % 2 == 0 else "B",
                "day": (i % 7) + 1 if dayed else None,
                "utm_parameters": {
                    "source": platform,
                    "medium": "paid" if asset_type == "ad_copy" else "social",
                    "campaign": "q3_growth",
                    "content": f"{asset_type}_{i}",
                    "term": None,
                },
                "ab_test": {
                    "variant_a": "Benefit-first copy",
                    "variant_b": "Pain-first copy",
                    "hypothesis": "Benefit framing improves CTR",
                },
                "metadata": {},
            }
        )
    return {"assets": assets}


@pytest.mark.asyncio
async def test_content_creator_node_success_with_batched_generation():
    responses = [
        json.dumps(
            {
                "assets": _build_batch("ad_copy", "google_ads", 3, 1)["assets"]
                + _build_batch("ad_copy", "meta_ads", 3, 4)["assets"]
                + _build_batch("ad_copy", "linkedin_ads", 3, 7)["assets"]
            }
        ),
        json.dumps(
            {
                "assets": _build_batch("social_post", "twitter_x", 5, 10, dayed=True)["assets"]
                + _build_batch("social_post", "linkedin", 5, 20, dayed=True)["assets"]
                + _build_batch("social_post", "instagram", 4, 30, dayed=True)["assets"]
            }
        ),
        json.dumps({"assets": _build_batch("email", "email", 3, 40)["assets"]}),
        json.dumps({"assets": _build_batch("landing_page", "landing_page", 1, 50)["assets"]}),
        json.dumps({"assets": _build_batch("visual_brief", "design", 3, 60)["assets"]}),
    ]

    llm = FakeLLM(responses)

    result = await content_creator_node(
        state={
            "campaign_strategy": _strategy_payload(),
            "brand_guidelines": _guidelines_payload(),
        },
        llm=llm,
    )

    assert result["agent_name"] == "content_creator"
    assert result["content_package"] is not None
    assert len(result["content_package"]["assets"]) == 30
    assert result["content_valid"] is True
    assert result["content_quality_issues"] == []


def test_validate_content_quality_detects_prohibited_and_length_issues():
    strategy = CampaignStrategy.model_validate(_strategy_payload())
    guidelines = BrandGuidelines.model_validate(_guidelines_payload())

    bad_package = {
        "assets": [
            {
                "asset_id": "bad-1",
                "asset_type": "social_post",
                "platform": "twitter_x",
                "persona_name": "Nonexistent Persona",
                "title": "",
                "body": "This guaranteed result message is way too long " + ("x" * 300),
                "cta": "",
                "variant": "A",
                "day": 1,
                "utm_parameters": {
                    "source": "",
                    "medium": "",
                    "campaign": "q3",
                    "content": "bad",
                    "term": None,
                },
                "ab_test": {
                    "variant_a": "A",
                    "variant_b": "B",
                    "hypothesis": "",
                },
                "metadata": {},
            }
        ]
    }

    from src.content_creator import ContentPackage

    package = ContentPackage.model_validate(bad_package)
    issues = validate_content_quality(package, strategy, guidelines)

    assert any("unknown persona reference" in issue for issue in issues)
    assert any("prohibited word" in issue for issue in issues)
    assert any("X post exceeds 280" in issue for issue in issues)
    assert any("missing UTM source/medium" in issue for issue in issues)
    assert any("Need at least 3 Google Ads variants" in issue for issue in issues)


@pytest.mark.asyncio
async def test_content_creator_supports_requested_channel_assets():
    responses = [
        json.dumps({"assets": _build_batch("ad_copy", "google_ads", 3, 1)["assets"] + _build_batch("ad_copy", "meta_ads", 3, 4)["assets"] + _build_batch("ad_copy", "linkedin_ads", 3, 7)["assets"]}),
        json.dumps({"assets": _build_batch("social_post", "linkedin", 7, 20, dayed=True)["assets"] + _build_batch("social_post", "facebook", 7, 30, dayed=True)["assets"]}),
        json.dumps({"assets": _build_batch("email", "email", 3, 40)["assets"]}),
        json.dumps({"assets": _build_batch("landing_page", "landing_page", 1, 50)["assets"]}),
        json.dumps({"assets": _build_batch("visual_brief", "design", 3, 60)["assets"]}),
    ]

    llm = FakeLLM(responses)
    result = await content_creator_node(
        state={"content_request": "Create content for LinkedIn, Facebook, Email, and Google Ads."},
        llm=llm,
    )

    assets = result["content_package"]["assets"]
    platforms = {asset["platform"] for asset in assets}

    assert "linkedin" in platforms
    assert "facebook" in platforms
    assert "email" in platforms
    assert "google_ads" in platforms
    assert any(asset["title"] for asset in assets if asset["platform"] == "google_ads")
    assert any(asset["body"] for asset in assets if asset["platform"] == "google_ads")
    assert any(asset["cta"] for asset in assets if asset["platform"] == "google_ads")


@pytest.mark.asyncio
async def test_content_creator_budget_zero_excludes_paid_ads():
    responses = [
        json.dumps({"assets": _build_batch("ad_copy", "google_ads", 3, 1)["assets"] + _build_batch("ad_copy", "meta_ads", 3, 4)["assets"] + _build_batch("ad_copy", "linkedin_ads", 3, 7)["assets"]}),
        json.dumps({"assets": _build_batch("social_post", "linkedin", 7, 20, dayed=True)["assets"] + _build_batch("social_post", "instagram", 7, 30, dayed=True)["assets"]}),
        json.dumps({"assets": _build_batch("email", "email", 3, 40)["assets"]}),
        json.dumps({"assets": _build_batch("landing_page", "landing_page", 1, 50)["assets"]}),
        json.dumps({"assets": _build_batch("visual_brief", "design", 3, 60)["assets"]}),
    ]

    llm = FakeLLM(responses)
    result = await content_creator_node(
        state={"content_request": "Budget = 0", "total_budget": 0},
        llm=llm,
    )

    assets = result["content_package"]["assets"]
    paid_platforms = {"google_ads", "meta_ads", "linkedin_ads"}
    assert all(asset["platform"] not in paid_platforms for asset in assets)


@pytest.mark.asyncio
async def test_content_creator_missing_audience_sets_assumptions():
    responses = [
        json.dumps({"assets": _build_batch("ad_copy", "google_ads", 3, 1)["assets"] + _build_batch("ad_copy", "meta_ads", 3, 4)["assets"] + _build_batch("ad_copy", "linkedin_ads", 3, 7)["assets"]}),
        json.dumps({"assets": _build_batch("social_post", "linkedin", 7, 20, dayed=True)["assets"] + _build_batch("social_post", "instagram", 7, 30, dayed=True)["assets"]}),
        json.dumps({"assets": _build_batch("email", "email", 3, 40)["assets"]}),
        json.dumps({"assets": _build_batch("landing_page", "landing_page", 1, 50)["assets"]}),
        json.dumps({"assets": _build_batch("visual_brief", "design", 3, 60)["assets"]}),
    ]

    llm = FakeLLM(responses)
    result = await content_creator_node(
        state={"content_request": "Create campaign content for Google Ads and Email."},
        llm=llm,
    )

    assert result["content_assumptions"]
