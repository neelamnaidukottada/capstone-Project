"""Media Buyer LangGraph node.

Builds a media plan from campaign strategy + content package + total budget.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, timedelta
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError, model_validator

from .content_creator import ContentPackage, Platform
from .planner import CampaignStrategy

logger = logging.getLogger(__name__)

AGENT_NAME = "media_buyer"


class TotalBudget(BaseModel):
    amount: float = Field(..., ge=0)


class DateRange(BaseModel):
    start_date: date
    end_date: date
    dayparting_recommendations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self) -> "DateRange":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class AudienceTargeting(BaseModel):
    demographics: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    behaviors: list[str] = Field(default_factory=list)
    lookalike_audiences: list[str] = Field(default_factory=list)


class ChannelPlan(BaseModel):
    channel: str
    budget: float = Field(..., ge=0)
    budget_percentage: float = Field(..., ge=0, le=100)
    bid_strategy: str
    targeting: AudienceTargeting
    projected_reach: int = Field(..., ge=0)
    projected_impressions: int = Field(..., ge=0)
    projected_clicks: int = Field(..., ge=0)
    projected_conversions: int = Field(..., ge=0)
    rationale: str


class MediaPlan(BaseModel):
    channels: list[ChannelPlan] = Field(default_factory=list)
    total_budget: float = Field(..., ge=0)
    daily_budget: float = Field(..., ge=0)
    bid_strategy: str
    targeting: AudienceTargeting
    flight_dates: DateRange

    @model_validator(mode="after")
    def validate_budget_sum(self) -> "MediaPlan":
        allocated = sum(ch.budget for ch in self.channels)
        if self.total_budget == 0 and allocated == 0:
            return self
        if abs(allocated - self.total_budget) > 0.05:
            raise ValueError(
                f"Channel budgets ({allocated:.2f}) must sum to total_budget ({self.total_budget:.2f})"
            )
        return self


SYSTEM_PROMPT = """You are an elite digital media buying strategist with deep expertise in Google Ads, Meta Ads, and LinkedIn Ads.

You optimize for efficiency and scale by balancing:
- Objective fit (awareness, conversion, retention)
- Audience-platform affinity
- Historical benchmark performance
- Seasonality and timing windows

When asked for rationale text, be concise, quantitative, and practical.
"""


OBJECTIVE_WEIGHTS: dict[str, dict[str, float]] = {
    "awareness": {"google_ads": 0.25, "meta_ads": 0.35, "linkedin_ads": 0.15, "youtube": 0.15, "display": 0.10},
    "conversion": {"google_ads": 0.45, "meta_ads": 0.20, "linkedin_ads": 0.15, "youtube": 0.10, "display": 0.10},
    "retention": {"google_ads": 0.20, "meta_ads": 0.25, "linkedin_ads": 0.30, "youtube": 0.10, "display": 0.15},
}


class SimulatedGoogleAdsAPI:
    """Simulated Google Ads benchmark API."""

    async def get_benchmarks(self, objective: str, seasonality: float) -> dict[str, float]:
        base = {
            "awareness": {"cpm": 7.5, "ctr": 0.018, "cvr": 0.020},
            "conversion": {"cpm": 11.0, "ctr": 0.028, "cvr": 0.045},
            "retention": {"cpm": 8.5, "ctr": 0.022, "cvr": 0.035},
        }[objective]
        return {
            "cpm": base["cpm"] * seasonality,
            "ctr": base["ctr"],
            "cvr": base["cvr"],
        }


class SimulatedMetaAdsAPI:
    """Simulated Meta Ads benchmark API."""

    async def get_benchmarks(self, objective: str, seasonality: float) -> dict[str, float]:
        base = {
            "awareness": {"cpm": 6.0, "ctr": 0.014, "cvr": 0.015},
            "conversion": {"cpm": 9.5, "ctr": 0.020, "cvr": 0.030},
            "retention": {"cpm": 7.0, "ctr": 0.017, "cvr": 0.028},
        }[objective]
        return {
            "cpm": base["cpm"] * seasonality,
            "ctr": base["ctr"],
            "cvr": base["cvr"],
        }


def _linkedin_benchmarks(objective: str, seasonality: float) -> dict[str, float]:
    base = {
        "awareness": {"cpm": 14.0, "ctr": 0.010, "cvr": 0.010},
        "conversion": {"cpm": 18.0, "ctr": 0.012, "cvr": 0.022},
        "retention": {"cpm": 15.0, "ctr": 0.011, "cvr": 0.020},
    }[objective]
    return {
        "cpm": base["cpm"] * seasonality,
        "ctr": base["ctr"],
        "cvr": base["cvr"],
    }


def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(model="gpt-4o", temperature=0.2)


def _infer_objective(strategy: CampaignStrategy) -> str:
    text = " ".join(strategy.objectives + strategy.key_messages).lower()
    if any(word in text for word in ["awareness", "reach", "impression", "brand"]):
        return "awareness"
    if any(word in text for word in ["retain", "churn", "repeat", "reactivation"]):
        return "retention"
    return "conversion"


def _seasonality_multiplier(start: date) -> float:
    # Simple seasonality assumptions for paid media cost pressure.
    if start.month in {11, 12}:  # peak auction competition
        return 1.25
    if start.month in {7, 8}:    # lower competition in many B2B categories
        return 0.92
    return 1.0


def _platform_preference_scores(strategy: CampaignStrategy) -> dict[str, float]:
    # Rule-based audience affinity from persona descriptors.
    score = {"google_ads": 1.0, "meta_ads": 1.0, "linkedin_ads": 1.0}

    corpus = " ".join(
        item
        for p in strategy.target_audiences
        for item in ([p.segment] + p.demographics + p.pain_points + p.motivations)
    ).lower()

    b2b_terms = ["director", "manager", "enterprise", "b2b", "professional", "saas"]
    b2c_terms = ["consumer", "lifestyle", "shopping", "creator", "d2c", "ecommerce"]

    if any(term in corpus for term in b2b_terms):
        score["linkedin_ads"] += 0.5
        score["google_ads"] += 0.2
    if any(term in corpus for term in b2c_terms):
        score["meta_ads"] += 0.5

    return score


def _extract_available_paid_channels(content_package: ContentPackage) -> list[str]:
    mapping = {
        Platform.GOOGLE_ADS: "google_ads",
        Platform.META_ADS: "meta_ads",
        Platform.LINKEDIN_ADS: "linkedin_ads",
        Platform.FACEBOOK: "facebook",
        Platform.INSTAGRAM: "instagram",
        Platform.TIKTOK: "tiktok",
        Platform.YOUTUBE: "youtube",
    }
    channels: list[str] = []
    for asset in content_package.assets:
        if asset.platform in mapping:
            channel = mapping[asset.platform]
            if channel not in channels:
                channels.append(channel)

    return channels or ["google_ads", "meta_ads", "linkedin_ads"]


def _audience_corpus(strategy: CampaignStrategy) -> str:
    return " ".join(
        item
        for p in strategy.target_audiences
        for item in ([p.segment] + p.demographics + p.pain_points + p.motivations)
    ).lower()


def _select_channels_for_context(
    strategy: CampaignStrategy,
    available_channels: list[str],
    total_budget: float,
) -> list[str]:
    corpus = _audience_corpus(strategy)

    if total_budget <= 5000 and any(term in corpus for term in ["student", "college", "university", "gen z"]):
        return ["instagram", "tiktok", "youtube"]

    if total_budget >= 250000:
        return ["google_ads", "linkedin_ads", "facebook", "display", "youtube"]

    return available_channels


def _bid_strategy_for_objective(objective: str) -> str:
    if objective == "awareness":
        return "manual CPC"
    if objective == "retention":
        return "maximize conversions"
    return "target CPA"


def _dayparting_recommendations(objective: str) -> list[str]:
    if objective == "awareness":
        return [
            "Prioritize 7:00-10:00 and 18:00-22:00 local time for broad reach",
            "Cap overnight spend (00:00-05:00) unless low-cost inventory is verified",
        ]
    if objective == "retention":
        return [
            "Prioritize 8:00-11:00 and 17:00-21:00 to capture existing users post-work",
            "Increase bids during remarketing windows after email sends",
        ]
    return [
        "Prioritize 09:00-18:00 business hours for high-intent conversion traffic",
        "Use bid multipliers for top-performing weekdays after first 7 days",
    ]


def _build_targeting(strategy: CampaignStrategy) -> AudienceTargeting:
    demographics: list[str] = []
    interests: list[str] = []
    behaviors: list[str] = []

    for persona in strategy.target_audiences:
        demographics.extend(persona.demographics)
        interests.extend(persona.motivations)
        behaviors.extend(persona.pain_points)

    dedupe = lambda xs: list(dict.fromkeys(x for x in xs if x))

    return AudienceTargeting(
        demographics=dedupe(demographics)[:12],
        interests=dedupe(interests)[:12],
        behaviors=dedupe(behaviors)[:12],
        lookalike_audiences=[
            "Lookalike of high-intent site visitors (30d)",
            "Lookalike of MQL / SQL converters",
        ],
    )


def _projection(budget: float, cpm: float, ctr: float, cvr: float) -> tuple[int, int, int, int]:
    if budget <= 0 or cpm <= 0:
        return 0, 0, 0, 0
    impressions = int((budget / cpm) * 1000)
    # Reach multiplier assumptions by platform auction frequency.
    reach = int(impressions * 0.62)
    clicks = int(impressions * ctr)
    conversions = int(clicks * cvr)
    return reach, impressions, clicks, conversions


def _rule_based_budget_split(
    objective: str,
    available_channels: list[str],
    preference_score: dict[str, float],
    benchmarks: dict[str, dict[str, float]],
    total_budget: float,
) -> dict[str, float]:
    if total_budget <= 0:
        return {channel: 0.0 for channel in available_channels}

    if len(available_channels) == 1:
        return {available_channels[0]: round(total_budget, 2)}

    # Student-focused low budgets prioritize social video channels.
    if set(available_channels) == {"instagram", "tiktok", "youtube"} and total_budget <= 5000:
        return {
            "instagram": round(total_budget * 0.40, 2),
            "tiktok": round(total_budget * 0.35, 2),
            "youtube": round(total_budget * 0.25, 2),
        }

    # High-budget omni-channel allocation template.
    if set(available_channels) == {"google_ads", "linkedin_ads", "facebook", "display", "youtube"} and total_budget >= 250000:
        return {
            "google_ads": round(total_budget * 0.30, 2),
            "linkedin_ads": round(total_budget * 0.20, 2),
            "facebook": round(total_budget * 0.18, 2),
            "display": round(total_budget * 0.15, 2),
            "youtube": round(total_budget * 0.17, 2),
        }

    base_weights = OBJECTIVE_WEIGHTS[objective]
    weighted: dict[str, float] = {}

    for channel in available_channels:
        bench = benchmarks[channel]
        perf_score = (bench["ctr"] * max(bench["cvr"], 0.001)) / max(bench["cpm"], 0.001)
        weighted[channel] = base_weights.get(channel, 0.2) * preference_score.get(channel, 1.0) * perf_score

    total_weight = sum(weighted.values())
    if total_weight <= 0:
        even = round(total_budget / len(available_channels), 2)
        split = {ch: even for ch in available_channels}
        split[available_channels[-1]] = round(total_budget - sum(split.values()) + split[available_channels[-1]], 2)
        return split

    split: dict[str, float] = {}
    running = 0.0
    for idx, channel in enumerate(available_channels):
        if idx == len(available_channels) - 1:
            split[channel] = round(total_budget - running, 2)
            break
        amount = round(total_budget * (weighted[channel] / total_weight), 2)
        split[channel] = amount
        running += amount

    return split


async def _maybe_generate_llm_rationale(
    llm: ChatOpenAI | None,
    channel: str,
    objective: str,
    budget: float,
    benchmark: dict[str, float],
) -> str | None:
    if llm is None:
        return None

    prompt_payload = {
        "channel": channel,
        "objective": objective,
        "budget": budget,
        "benchmark": benchmark,
    }
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(prompt_payload)),
    ]
    try:
        response = await llm.ainvoke(messages)
        content = response.content
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return "".join(part.get("text", "") for part in content if isinstance(part, dict)).strip()
        return None
    except Exception:
        logger.warning("Falling back to deterministic rationale for %s", channel)
        return None


async def media_buyer_node(
    state: dict[str, Any],
    max_retries: int = 2,
    llm: ChatOpenAI | None = None,
) -> dict[str, Any]:
    """LangGraph node for media planning.

    Expected state keys:
    - campaign_strategy: dict | CampaignStrategy
    - content_package: dict | ContentPackage
    - total_budget: float | dict { amount: float }
    """
    raw_strategy = state.get("campaign_strategy")
    raw_content = state.get("content_package")
    raw_budget = state.get("total_budget")

    if raw_strategy is None:
        raise ValueError("Missing required state key: campaign_strategy")
    if raw_content is None:
        raise ValueError("Missing required state key: content_package")
    if raw_budget is None:
        raise ValueError("Missing required state key: total_budget")

    strategy = (
        raw_strategy if isinstance(raw_strategy, CampaignStrategy) else CampaignStrategy.model_validate(raw_strategy)
    )
    content_package = (
        raw_content if isinstance(raw_content, ContentPackage) else ContentPackage.model_validate(raw_content)
    )

    if isinstance(raw_budget, dict):
        total_budget_model = TotalBudget.model_validate(raw_budget)
        total_budget = total_budget_model.amount
    else:
        total_budget = TotalBudget(amount=float(raw_budget)).amount

    start = date.today()
    max_day = max((m.day for m in strategy.timeline), default=30)
    end = start + timedelta(days=max(1, max_day))

    objective = _infer_objective(strategy)
    bid_strategy = _bid_strategy_for_objective(objective)
    targeting = _build_targeting(strategy)

    if total_budget == 0:
        plan = MediaPlan(
            channels=[],
            total_budget=0.0,
            daily_budget=0.0,
            bid_strategy=bid_strategy,
            targeting=targeting,
            flight_dates=DateRange(
                start_date=start,
                end_date=end,
                dayparting_recommendations=_dayparting_recommendations(objective),
            ),
        )
        return {
            "agent_name": AGENT_NAME,
            "media_plan": plan.model_dump(mode="json"),
            "media_plan_valid": True,
            "media_plan_issues": [],
        }

    seasonality = _seasonality_multiplier(start)
    available_channels = _extract_available_paid_channels(content_package)
    preference = _platform_preference_scores(strategy)

    google_api = SimulatedGoogleAdsAPI()
    meta_api = SimulatedMetaAdsAPI()

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            google_bench, meta_bench = await asyncio.gather(
                google_api.get_benchmarks(objective, seasonality),
                meta_api.get_benchmarks(objective, seasonality),
            )
            benchmarks = {
                "google_ads": google_bench,
                "meta_ads": meta_bench,
                "linkedin_ads": _linkedin_benchmarks(objective, seasonality),
                "instagram": {
                    "cpm": meta_bench["cpm"] * 0.95,
                    "ctr": max(meta_bench["ctr"], 0.012),
                    "cvr": max(meta_bench["cvr"], 0.012),
                },
                "facebook": {
                    "cpm": meta_bench["cpm"] * 1.05,
                    "ctr": max(meta_bench["ctr"], 0.010),
                    "cvr": max(meta_bench["cvr"], 0.010),
                },
                "tiktok": {
                    "cpm": 5.8 * seasonality,
                    "ctr": 0.016,
                    "cvr": 0.014,
                },
                "youtube": {
                    "cpm": 8.2 * seasonality,
                    "ctr": 0.012,
                    "cvr": 0.012,
                },
                "display": {
                    "cpm": 4.2 * seasonality,
                    "ctr": 0.006,
                    "cvr": 0.008,
                },
            }

            selected_channels = _select_channels_for_context(
                strategy=strategy,
                available_channels=available_channels,
                total_budget=total_budget,
            )

            split = _rule_based_budget_split(
                objective=objective,
                available_channels=selected_channels,
                preference_score=preference,
                benchmarks=benchmarks,
                total_budget=total_budget,
            )

            llm_client = llm
            if llm_client is None:
                try:
                    llm_client = _build_llm()
                except Exception:
                    llm_client = None

            rationale_tasks = [
                _maybe_generate_llm_rationale(
                    llm=llm_client,
                    channel=channel,
                    objective=objective,
                    budget=budget,
                    benchmark=benchmarks[channel],
                )
                for channel, budget in split.items()
            ]
            llm_rationales = await asyncio.gather(*rationale_tasks)

            channels: list[ChannelPlan] = []
            for idx, (channel, budget) in enumerate(split.items()):
                bench = benchmarks[channel]
                reach, impressions, clicks, conversions = _projection(
                    budget=budget,
                    cpm=bench["cpm"],
                    ctr=bench["ctr"],
                    cvr=bench["cvr"],
                )
                deterministic_rationale = (
                    f"Allocated {budget:.2f} ({(budget / total_budget) * 100:.1f}%) to {channel} based on "
                    f"objective fit ({objective}), audience preference score ({preference.get(channel, 1.0):.2f}), "
                    f"and benchmark efficiency (CPM={bench['cpm']:.2f}, CTR={bench['ctr']:.3f}, CVR={bench['cvr']:.3f})."
                )
                channel_rationale = llm_rationales[idx] or deterministic_rationale

                channels.append(
                    ChannelPlan(
                        channel=channel,
                        budget=budget,
                        budget_percentage=round((budget / total_budget) * 100, 2),
                        bid_strategy=bid_strategy,
                        targeting=targeting,
                        projected_reach=reach,
                        projected_impressions=impressions,
                        projected_clicks=clicks,
                        projected_conversions=conversions,
                        rationale=channel_rationale,
                    )
                )

            total_days = max((end - start).days, 1)
            plan = MediaPlan(
                channels=channels,
                total_budget=round(total_budget, 2),
                daily_budget=round(total_budget / total_days, 2),
                bid_strategy=bid_strategy,
                targeting=targeting,
                flight_dates=DateRange(
                    start_date=start,
                    end_date=end,
                    dayparting_recommendations=_dayparting_recommendations(objective),
                ),
            )

            return {
                "agent_name": AGENT_NAME,
                "media_plan": plan.model_dump(mode="json"),
                "media_plan_valid": True,
                "media_plan_issues": [],
            }
        except (ValidationError, ValueError, RuntimeError) as exc:
            last_error = exc
            logger.warning("media_buyer attempt %s/%s failed: %s", attempt, max_retries, exc)
            if attempt == max_retries:
                break
        except Exception as exc:  # defensive catch for unexpected provider/runtime errors
            last_error = exc
            logger.exception("media_buyer provider/runtime failure on attempt %s/%s", attempt, max_retries)
            if attempt == max_retries:
                break

    return {
        "agent_name": AGENT_NAME,
        "media_plan": None,
        "media_plan_valid": False,
        "media_plan_issues": [str(last_error) if last_error else "Unknown media buyer error"],
        "media_plan_error": str(last_error) if last_error else "Unknown media buyer error",
    }
