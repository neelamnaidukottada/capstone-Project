"""Content Creator LangGraph node.

Generates multi-channel campaign assets from campaign strategy + brand guidelines.
"""

from __future__ import annotations

import asyncio
import json
import logging
from enum import Enum
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError

from .planner import CampaignStrategy

logger = logging.getLogger(__name__)

AGENT_NAME = "content_creator"


class BrandGuidelines(BaseModel):
    tone: str = Field(..., min_length=2)
    voice: str = Field(..., min_length=2)
    prohibited_words: list[str] = Field(default_factory=list)
    brand_colors: list[str] = Field(default_factory=list)


class AssetType(str, Enum):
    AD_COPY = "ad_copy"
    SOCIAL_POST = "social_post"
    EMAIL = "email"
    LANDING_PAGE = "landing_page"
    VISUAL_BRIEF = "visual_brief"


class Platform(str, Enum):
    GOOGLE_ADS = "google_ads"
    META_ADS = "meta_ads"
    LINKEDIN_ADS = "linkedin_ads"
    FACEBOOK = "facebook"
    TWITTER_X = "twitter_x"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    EMAIL = "email"
    LANDING_PAGE = "landing_page"
    DESIGN = "design"


class ABTestSpec(BaseModel):
    variant_a: str
    variant_b: str
    hypothesis: str


class UTMParams(BaseModel):
    source: str
    medium: str
    campaign: str
    content: str
    term: str | None = None


class ContentAsset(BaseModel):
    asset_id: str
    asset_type: AssetType
    platform: Platform
    persona_name: str
    title: str = ""
    body: str
    cta: str = ""
    variant: str = Field(default="A")
    day: int | None = Field(default=None, ge=1, le=7)
    utm_parameters: UTMParams
    ab_test: ABTestSpec
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContentPackage(BaseModel):
    assets: list[ContentAsset] = Field(default_factory=list)


class ContentAssetBatch(BaseModel):
    assets: list[ContentAsset] = Field(default_factory=list)


SYSTEM_PROMPT = """You are a senior content marketing lead and performance copywriter.

Best-practice rules:
- Match each asset to a clear buyer persona and pain point.
- Keep voice and tone consistent with brand guidelines.
- Write platform-native copy and respect character limits.
- Include clear CTA and measurable intent.
- Provide A/B test angles with hypothesis.
- Add practical UTM suggestions for tracking.

Character limits:
- Google Ads headline <= 30, description <= 90
- Meta Ads primary text <= 125, headline <= 40
- LinkedIn Ads intro <= 150, headline <= 70
- X post <= 280
- LinkedIn post <= 3000
- Instagram caption <= 2200
- Email subject <= 78
- Landing headline <= 70, subheadline <= 160, CTA <= 30

Few-shot mini example:
Input persona: "Growth-Focused Marketing Manager"
Good ad line: "Cut campaign launch time by 60% in 30 days"
Weak ad line: "Best tool ever" (too vague, not benefit-driven)

Output strict JSON only matching schema exactly.
"""


def _json_schema_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "content_asset_batch",
            "schema": ContentAssetBatch.model_json_schema(),
            "strict": True,
        },
    }


def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o",
        temperature=0.4,
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


def _persona_names(strategy: CampaignStrategy) -> list[str]:
    return [p.name for p in strategy.target_audiences]


def _is_awareness_strategy(strategy: CampaignStrategy) -> bool:
    corpus = " ".join(strategy.objectives + strategy.key_messages).lower()
    return any(token in corpus for token in ["awareness", "brand", "reach", "impression"])


def _extract_budget_hint(state: dict[str, Any]) -> float | None:
    raw_budget = state.get("total_budget")
    if raw_budget is not None:
        try:
            return float(raw_budget)
        except (TypeError, ValueError):
            return None

    raw_request = state.get("content_request")
    if isinstance(raw_request, str):
        import re

        match = re.search(r"budget\s*[:=]?\s*\$?\s*(-?\d+(?:\.\d+)?)", raw_request, flags=re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
    return None


def _strategy_from_content_request(content_request: str) -> CampaignStrategy:
    request_lower = content_request.lower()

    channels = []
    if "linkedin" in request_lower:
        channels.append(
            {
                "channel": "LinkedIn",
                "budget_percentage": 30,
                "rationale": "B2B professional audience concentration",
                "execution_notes": ["Use thought-leadership and product proof"],
            }
        )
    if "facebook" in request_lower:
        channels.append(
            {
                "channel": "Facebook",
                "budget_percentage": 30,
                "rationale": "Broad awareness reach and retargeting",
                "execution_notes": ["Use social proof and short-form hooks"],
            }
        )
    if "google" in request_lower:
        channels.append(
            {
                "channel": "Google Ads",
                "budget_percentage": 40,
                "rationale": "Capture active search intent",
                "execution_notes": ["Use intent-based ad groups"],
            }
        )

    return CampaignStrategy.model_validate(
        {
            "objectives": ["Create multi-channel campaign assets for requested platforms"],
            "target_audiences": [
                {
                    "name": "Primary Audience Assumption",
                    "segment": "General professionals",
                    "demographics": ["Assumed working-age audience"],
                    "pain_points": ["Time constraints", "Information overload"],
                    "motivations": ["Efficiency", "Clear outcomes"],
                },
                {
                    "name": "Secondary Decision Maker",
                    "segment": "Team leads and managers",
                    "demographics": ["B2B/B2C decision influencers"],
                    "pain_points": ["Performance pressure"],
                    "motivations": ["Reliable ROI"],
                },
            ],
            "key_messages": ["Clear value proposition tailored by channel"],
            "recommended_channels": channels,
            "timeline": [
                {
                    "day": 1,
                    "title": "Draft creation",
                    "description": "Generate channel-specific variants",
                    "success_criteria": "Assets ready for review",
                }
            ],
            "budget_allocation": {},
            "competitive_differentiation": ["Message-market fit by channel"],
            "confidence_score": 0.72,
        }
    )


def _default_guidelines() -> BrandGuidelines:
    return BrandGuidelines(
        tone="clear",
        voice="helpful expert",
        prohibited_words=[],
        brand_colors=[],
    )


def validate_content_quality(
    content_package: ContentPackage,
    strategy: CampaignStrategy,
    brand_guidelines: BrandGuidelines,
) -> list[str]:
    """Return validation issues; empty list means content is valid enough to publish."""
    issues: list[str] = []
    valid_personas = set(_persona_names(strategy))
    prohibited = [w.lower() for w in brand_guidelines.prohibited_words]
    awareness_mode = _is_awareness_strategy(strategy)
    sales_terms = ["buy now", "purchase", "limited time offer", "discount", "sale"]

    for asset in content_package.assets:
        if asset.persona_name not in valid_personas:
            issues.append(f"{asset.asset_id}: unknown persona reference '{asset.persona_name}'")

        body_lower = asset.body.lower()
        title_lower = asset.title.lower()
        cta_lower = asset.cta.lower()
        for banned in prohibited:
            if banned and (banned in body_lower or banned in title_lower or banned in cta_lower):
                issues.append(f"{asset.asset_id}: contains prohibited word '{banned}'")

        if awareness_mode and any(term in cta_lower for term in sales_terms):
            issues.append(f"{asset.asset_id}: sales CTA detected for awareness objective")

        # Character limits by platform and type
        if asset.asset_type == AssetType.AD_COPY and asset.platform == Platform.GOOGLE_ADS:
            if asset.title and len(asset.title) > 30:
                issues.append(f"{asset.asset_id}: Google Ads headline exceeds 30 chars")
            if len(asset.body) > 90:
                issues.append(f"{asset.asset_id}: Google Ads description exceeds 90 chars")
        elif asset.asset_type == AssetType.AD_COPY and asset.platform == Platform.META_ADS:
            if asset.title and len(asset.title) > 40:
                issues.append(f"{asset.asset_id}: Meta Ads headline exceeds 40 chars")
            if len(asset.body) > 125:
                issues.append(f"{asset.asset_id}: Meta Ads primary text exceeds 125 chars")
        elif asset.asset_type == AssetType.AD_COPY and asset.platform == Platform.LINKEDIN_ADS:
            if asset.title and len(asset.title) > 70:
                issues.append(f"{asset.asset_id}: LinkedIn Ads headline exceeds 70 chars")
            if len(asset.body) > 150:
                issues.append(f"{asset.asset_id}: LinkedIn Ads intro exceeds 150 chars")
        elif asset.asset_type == AssetType.SOCIAL_POST and asset.platform == Platform.TWITTER_X:
            if len(asset.body) > 280:
                issues.append(f"{asset.asset_id}: X post exceeds 280 chars")
        elif asset.asset_type == AssetType.SOCIAL_POST and asset.platform == Platform.LINKEDIN:
            if len(asset.body) > 3000:
                issues.append(f"{asset.asset_id}: LinkedIn post exceeds 3000 chars")
        elif asset.asset_type == AssetType.SOCIAL_POST and asset.platform == Platform.INSTAGRAM:
            if len(asset.body) > 2200:
                issues.append(f"{asset.asset_id}: Instagram caption exceeds 2200 chars")
        elif asset.asset_type == AssetType.EMAIL:
            if asset.title and len(asset.title) > 78:
                issues.append(f"{asset.asset_id}: Email subject exceeds 78 chars")
        elif asset.asset_type == AssetType.LANDING_PAGE:
            if asset.title and len(asset.title) > 70:
                issues.append(f"{asset.asset_id}: Landing headline exceeds 70 chars")
            if len(asset.body) > 160:
                issues.append(f"{asset.asset_id}: Landing subheadline exceeds 160 chars")
            if asset.cta and len(asset.cta) > 30:
                issues.append(f"{asset.asset_id}: Landing CTA exceeds 30 chars")

        # Ensure tracking and experiments are present.
        if not asset.utm_parameters.source or not asset.utm_parameters.medium:
            issues.append(f"{asset.asset_id}: missing UTM source/medium")
        if not asset.ab_test.hypothesis:
            issues.append(f"{asset.asset_id}: missing A/B test hypothesis")

    # Required inventory checks
    ad_assets = [a for a in content_package.assets if a.asset_type == AssetType.AD_COPY]
    google = [a for a in ad_assets if a.platform == Platform.GOOGLE_ADS]
    meta = [a for a in ad_assets if a.platform == Platform.META_ADS]
    linkedin_ads = [a for a in ad_assets if a.platform == Platform.LINKEDIN_ADS]

    if len(google) < 3:
        issues.append("Need at least 3 Google Ads variants")
    if len(meta) < 3:
        issues.append("Need at least 3 Meta Ads variants")
    if len(linkedin_ads) < 3:
        issues.append("Need at least 3 LinkedIn Ads variants")

    social_assets = [a for a in content_package.assets if a.asset_type == AssetType.SOCIAL_POST]
    if len(social_assets) < 14:
        issues.append("Need at least 14 social posts (7 days x 2 posts/day)")

    email_assets = [a for a in content_package.assets if a.asset_type == AssetType.EMAIL]
    if len(email_assets) < 3:
        issues.append("Need a 3-email nurture sequence")

    landing_assets = [a for a in content_package.assets if a.asset_type == AssetType.LANDING_PAGE]
    if len(landing_assets) < 1:
        issues.append("Need landing page copy asset")

    visual_assets = [a for a in content_package.assets if a.asset_type == AssetType.VISUAL_BRIEF]
    if len(visual_assets) < 1:
        issues.append("Need at least one visual brief")

    return issues


async def _generate_batch(
    llm: ChatOpenAI,
    strategy: CampaignStrategy,
    brand_guidelines: BrandGuidelines,
    instruction: str,
    max_retries: int,
) -> list[ContentAsset]:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=json.dumps(
                {
                    "instruction": instruction,
                    "campaign_strategy": strategy.model_dump(),
                    "brand_guidelines": brand_guidelines.model_dump(),
                }
            )
        ),
    ]

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = await llm.ainvoke(messages)
            parsed = _parse_llm_content(response.content)
            batch = ContentAssetBatch.model_validate(parsed)
            return batch.assets
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            logger.warning("content_creator batch failed attempt %s/%s: %s", attempt, max_retries, exc)
            if attempt == max_retries:
                break

    raise RuntimeError(str(last_error) if last_error else "Unknown content generation error")


async def content_creator_node(
    state: dict[str, Any],
    max_retries: int = 3,
    llm: ChatOpenAI | None = None,
) -> dict[str, Any]:
    """LangGraph node that generates a ContentPackage from strategy + brand guidelines."""
    raw_strategy = state.get("campaign_strategy")
    raw_guidelines = state.get("brand_guidelines")
    content_request = state.get("content_request")

    if raw_strategy is None and isinstance(content_request, str):
        raw_strategy = _strategy_from_content_request(content_request)
    if raw_guidelines is None:
        raw_guidelines = _default_guidelines().model_dump()

    if raw_strategy is None:
        raise ValueError("Missing required state key: campaign_strategy")

    strategy = (
        raw_strategy
        if isinstance(raw_strategy, CampaignStrategy)
        else CampaignStrategy.model_validate(raw_strategy)
    )
    guidelines = (
        raw_guidelines
        if isinstance(raw_guidelines, BrandGuidelines)
        else BrandGuidelines.model_validate(raw_guidelines)
    )

    model = llm or _build_llm()

    # Batch generation for efficiency: run 5 section prompts concurrently.
    batch_instructions = [
        (
            "Generate ad copy assets only: exactly 9 assets total (3 Google Ads, 3 Meta Ads, "
            "3 LinkedIn Ads). Include title, body, CTA, persona_name, UTM params, A/B test spec."
        ),
        (
            "Generate social assets only: exactly 14 assets for a 7-day calendar, 2 posts/day across "
            "Twitter/X, LinkedIn, Instagram. Include day field for each post and persona_name."
        ),
        (
            "Generate email assets only: exactly 3 nurture emails with subject (title), body, CTA, "
            "persona reference, UTM params, and A/B test spec."
        ),
        (
            "Generate one landing page copy asset with headline in title, subheadline in body, CTA, "
            "persona reference, UTM params, and A/B test spec."
        ),
        (
            "Generate visual brief assets for designers: at least 3 visual_brief assets describing scene, "
            "layout, color usage from brand_colors, persona context, and CTA placement."
        ),
    ]

    try:
        results = await asyncio.gather(
            *[
                _generate_batch(model, strategy, guidelines, instruction, max_retries)
                for instruction in batch_instructions
            ]
        )
        all_assets = [asset for batch in results for asset in batch]

        budget_hint = _extract_budget_hint(state)
        if budget_hint is not None and budget_hint <= 0:
            all_assets = [
                asset
                for asset in all_assets
                if not (
                    asset.asset_type == AssetType.AD_COPY
                    and asset.platform in {Platform.GOOGLE_ADS, Platform.META_ADS, Platform.LINKEDIN_ADS}
                )
            ]

        content_package = ContentPackage(assets=all_assets)

        issues = validate_content_quality(content_package, strategy, guidelines)

        assumptions: list[str] = []
        if isinstance(content_request, str) and "audience" not in content_request.lower():
            assumptions.append("Audience was not specified; generated using reasonable default personas.")

        return {
            "agent_name": AGENT_NAME,
            "content_package": content_package.model_dump(),
            "content_quality_issues": issues,
            "content_valid": len(issues) == 0,
            "content_assumptions": assumptions,
        }
    except Exception as exc:
        logger.exception("content_creator failed")
        return {
            "agent_name": AGENT_NAME,
            "content_package": None,
            "content_quality_issues": [str(exc)],
            "content_valid": False,
            "content_error": str(exc),
        }
