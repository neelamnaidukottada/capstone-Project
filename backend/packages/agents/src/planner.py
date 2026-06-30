"""Strategic Planner LangGraph node.

This module defines:
- Pydantic input/output contracts
- A senior-strategist system prompt with few-shot examples
- A LangGraph-compatible async node function with retry logic
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

AGENT_NAME = "strategic_planner"


class CampaignGoal(BaseModel):
    goal: str = Field(..., min_length=5, description="Business objective to achieve")
    budget: float = Field(..., gt=0, description="Total campaign budget in USD")
    timeline_days: int = Field(..., gt=0, le=3650, description="Campaign duration in days")
    industry: str = Field(..., min_length=2)
    product_description: str = Field(..., min_length=15)


class Persona(BaseModel):
    name: str
    segment: str
    demographics: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    motivations: list[str] = Field(default_factory=list)


class ChannelStrategy(BaseModel):
    channel: str
    budget_percentage: float = Field(..., ge=0, le=100)
    rationale: str
    execution_notes: list[str] = Field(default_factory=list)


class Milestone(BaseModel):
    day: int = Field(..., ge=1)
    title: str
    description: str
    success_criteria: str


class CampaignStrategy(BaseModel):
    objectives: list[str] = Field(
        default_factory=list,
        description="SMART objectives (specific, measurable, achievable, relevant, time-bound)",
    )
    target_audiences: list[Persona] = Field(default_factory=list)
    key_messages: list[str] = Field(default_factory=list)
    recommended_channels: list[ChannelStrategy] = Field(default_factory=list)
    timeline: list[Milestone] = Field(default_factory=list)
    budget_allocation: dict[str, float] = Field(default_factory=dict)
    kpis: list[str] = Field(default_factory=list)
    funnel_strategy: list[str] = Field(default_factory=list)
    lead_magnet_suggestions: list[str] = Field(default_factory=list)
    competitive_differentiation: list[str] = Field(default_factory=list)
    confidence_score: float = Field(..., ge=0, le=1)


def _is_awareness_goal(goal_text: str) -> bool:
    text = goal_text.lower()
    return any(token in text for token in ["awareness", "brand awareness", "reach", "visibility"])


def _is_lead_generation_goal(goal_text: str) -> bool:
    text = goal_text.lower()
    return any(token in text for token in ["lead", "b2b leads", "mql", "sql", "pipeline"])


def _apply_intent_defaults(strategy: CampaignStrategy, goal: CampaignGoal) -> CampaignStrategy:
    goal_text = f"{goal.goal} {goal.product_description}"

    if _is_awareness_goal(goal_text):
        if not any("awareness" in obj.lower() for obj in strategy.objectives):
            strategy.objectives.insert(
                0,
                f"Increase brand awareness and qualified reach within {goal.timeline_days} days.",
            )

        if not strategy.kpis:
            strategy.kpis.extend([
                "Reach",
                "Impressions",
                "Engagement rate",
                "Share of voice",
            ])

        known_channels = {c.channel.lower() for c in strategy.recommended_channels}
        for channel_name in ["Instagram", "LinkedIn", "Facebook"]:
            if channel_name.lower() not in known_channels:
                strategy.recommended_channels.append(
                    ChannelStrategy(
                        channel=channel_name,
                        budget_percentage=0,
                        rationale="Social channel fit for awareness amplification.",
                        execution_notes=["Optimize for reach and engagement KPIs"],
                    )
                )

    if _is_lead_generation_goal(goal_text):
        if not strategy.funnel_strategy:
            strategy.funnel_strategy.extend([
                "Top-of-funnel awareness content",
                "Mid-funnel lead capture with gated value",
                "Bottom-funnel nurture and sales qualification",
            ])

        if not strategy.lead_magnet_suggestions:
            strategy.lead_magnet_suggestions.extend([
                "Industry benchmark report",
                "ROI calculator",
                "B2B implementation checklist",
            ])

        if not strategy.target_audiences:
            strategy.target_audiences.extend(
                [
                    Persona(
                        name="Primary ICP",
                        segment="B2B decision makers",
                        demographics=["Mid-market organizations"],
                        pain_points=["Unclear ROI", "Slow lead qualification"],
                        motivations=["Predictable pipeline growth"],
                    ),
                    Persona(
                        name="Economic Buyer",
                        segment="Revenue leadership",
                        demographics=["Director+ roles"],
                        pain_points=["Budget pressure"],
                        motivations=["Efficiency and conversion quality"],
                    ),
                ]
            )

    return strategy


SYSTEM_PROMPT_TEMPLATE = """You are a senior marketing strategist with 15+ years of experience in B2B and B2C growth.

Your responsibilities:
1) Build a practical campaign strategy from a CampaignGoal input.
2) Produce SMART objectives only.
3) Create 2-3 detailed buyer personas (demographics, pain points, motivations).
4) Recommend channels and explain budget split rationale.
5) Include competitive differentiation suggestions.
6) Return a confidence score between 0 and 1.

Output requirements:
- Return STRICT JSON only, no markdown.
- JSON must match the provided schema exactly.
- Ensure budget_allocation values sum approximately to the total budget.

Few-shot Example #1
Input:
{
  "goal": "Generate qualified demo requests for a new cybersecurity SaaS",
  "budget": 120000,
  "timeline_days": 90,
  "industry": "Cybersecurity",
  "product_description": "AI-powered endpoint threat detection platform for mid-market companies"
}
Output:
{
  "objectives": [
    "Increase qualified demo requests by 35% within 90 days compared to the previous quarter.",
    "Reduce paid media cost-per-qualified-lead to under $280 by day 75.",
    "Achieve 18% landing page conversion rate from high-intent traffic by campaign end."
  ],
  "target_audiences": [
    {
      "name": "Security-First IT Director",
      "segment": "Mid-market IT leadership",
      "demographics": ["Age 32-50", "North America", "200-1000 employee firms"],
      "pain_points": ["Tool sprawl", "False positives", "Lean security team"],
      "motivations": ["Reduce incident response time", "Prove ROI quickly"]
    },
    {
      "name": "Compliance-Focused Ops Lead",
      "segment": "Regulated industry operations",
      "demographics": ["Age 30-55", "Healthcare/FinServ"],
      "pain_points": ["Audit pressure", "Reporting complexity"],
      "motivations": ["Pass audits", "Lower compliance workload"]
    }
  ],
  "key_messages": [
    "Stop threats before they spread with autonomous endpoint intelligence.",
    "Cut false positives and focus your team on real incidents.",
    "Deploy in days, not quarters, with measurable security ROI."
  ],
  "recommended_channels": [
    {
      "channel": "LinkedIn ABM",
      "budget_percentage": 35,
      "rationale": "High match for decision-makers and account-level targeting.",
      "execution_notes": ["Target IT Director titles", "Use customer proof ads"]
    },
    {
      "channel": "Google Search",
      "budget_percentage": 40,
      "rationale": "Captures active intent for endpoint security alternatives.",
      "execution_notes": ["Bid on competitor terms", "Use demo-focused LP"]
    },
    {
      "channel": "Retargeting + Email Nurture",
      "budget_percentage": 25,
      "rationale": "Improves conversion efficiency and lead warming.",
      "execution_notes": ["7-email sequence", "Persona-specific content"]
    }
  ],
  "timeline": [
    {"day": 1, "title": "Launch setup", "description": "Finalize ICP, creative, tracking", "success_criteria": "Tracking QA passed"},
    {"day": 30, "title": "Optimization sprint", "description": "Reallocate budget to top ad sets", "success_criteria": "CPL improved by 15%"},
    {"day": 75, "title": "Scale winners", "description": "Increase spend on profitable channels", "success_criteria": "SQL volume up 25%"}
  ],
  "budget_allocation": {
    "LinkedIn ABM": 42000,
    "Google Search": 48000,
    "Retargeting + Email Nurture": 30000
  },
  "competitive_differentiation": [
    "Emphasize faster time-to-value versus enterprise-heavy competitors.",
    "Highlight autonomous remediation where competitors offer only alerts.",
    "Use transparent ROI benchmarks in all conversion assets."
  ],
  "confidence_score": 0.86
}

Few-shot Example #2
Input:
{
  "goal": "Increase repeat purchases for a D2C skincare brand",
  "budget": 40000,
  "timeline_days": 60,
  "industry": "Beauty",
  "product_description": "Science-backed sensitive skin routines sold online"
}
Output notes:
- Use lifecycle segmentation (new, active, churn-risk).
- Include creator content + CRM channels.
- Provide at least 2 personas and 3 milestones.
"""


def _json_schema_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "campaign_strategy",
            "schema": CampaignStrategy.model_json_schema(),
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


def _extract_budget_usd(brief: str) -> float | None:
    match = re.search(r"budget\s*[:=-]?\s*\$?\s*([\d,]+(?:\.\d+)?)", brief, flags=re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def _extract_duration_days(brief: str) -> int | None:
    match = re.search(r"duration\s*[:=-]?\s*(\d+)\s*days?", brief, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _extract_target_audience(brief: str) -> str | None:
    match = re.search(r"target\s*[:=-]?\s*([^\n\.]+)", brief, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _extract_product_name(brief: str) -> str | None:
    patterns = [
        r"new\s+([^\.\n]+)",
        r"campaign\s+for\s+([^\.\n]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, brief, flags=re.IGNORECASE)
        if match:
            product = match.group(1).strip()
            if product:
                return product
    return None


def _normalize_campaign_goal_dict(raw_goal: dict[str, Any]) -> dict[str, Any]:
    goal_value = raw_goal.get("goal") or raw_goal.get("business_goal") or raw_goal.get("campaign_name")

    budget_value = raw_goal.get("budget")
    if budget_value is None:
        budget_value = raw_goal.get("budget_total")

    timeline_days_value = raw_goal.get("timeline_days")
    if timeline_days_value is None and raw_goal.get("start_date") and raw_goal.get("end_date"):
        start = date.fromisoformat(str(raw_goal["start_date"]))
        end = date.fromisoformat(str(raw_goal["end_date"]))
        timeline_days_value = max(1, (end - start).days)

    target = raw_goal.get("target") or raw_goal.get("target_audience")
    industry_value = raw_goal.get("industry") or target or "General"

    product_description_value = (
        raw_goal.get("product_description")
        or raw_goal.get("campaign_name")
        or raw_goal.get("business_goal")
        or "Product marketing campaign"
    )

    if target and str(target).lower() not in str(product_description_value).lower():
        product_description_value = f"{product_description_value} for {target}"

    return {
        "goal": goal_value,
        "budget": budget_value,
        "timeline_days": timeline_days_value,
        "industry": industry_value,
        "product_description": product_description_value,
    }


def _campaign_goal_from_brief(brief: str) -> dict[str, Any]:
    cleaned = re.sub(r"\s+", " ", brief).strip()

    budget = _extract_budget_usd(cleaned) or 1000.0
    duration_days = _extract_duration_days(cleaned) or 30
    target = _extract_target_audience(cleaned) or "General audience"
    product_name = _extract_product_name(cleaned) or "new product"

    first_sentence = cleaned.split(".")[0].strip()
    goal = first_sentence or f"Launch campaign for {product_name}"

    product_description = f"{product_name} targeting {target}"

    return {
        "goal": goal,
        "budget": budget,
        "timeline_days": duration_days,
        "industry": target,
        "product_description": product_description,
    }


def _coerce_campaign_goal(raw_goal: Any) -> CampaignGoal:
    if isinstance(raw_goal, CampaignGoal):
        return raw_goal

    if isinstance(raw_goal, str):
        return CampaignGoal.model_validate(_campaign_goal_from_brief(raw_goal))

    if isinstance(raw_goal, dict):
        if isinstance(raw_goal.get("brief"), str):
            merged = _campaign_goal_from_brief(raw_goal["brief"])
            merged.update({k: v for k, v in raw_goal.items() if k != "brief"})
            return CampaignGoal.model_validate(_normalize_campaign_goal_dict(merged))
        return CampaignGoal.model_validate(_normalize_campaign_goal_dict(raw_goal))

    raise ValueError("campaign_goal must be CampaignGoal, dict, or string brief")


async def strategic_planner_node(
    state: dict[str, Any],
    max_retries: int = 3,
    llm: ChatOpenAI | None = None,
) -> dict[str, Any]:
    """LangGraph node for campaign strategy planning.

    Expected state keys:
    - campaign_goal: dict | CampaignGoal

    Returns state patch with keys:
    - campaign_strategy: CampaignStrategy as dict
    - agent_name: "strategic_planner"
    - planner_confidence: float
    """
    raw_goal = state.get("campaign_goal")
    if raw_goal is None:
        raise ValueError("Missing required state key: campaign_goal")

    goal = _coerce_campaign_goal(raw_goal)
    model = llm or _build_llm()

    messages = [
        SystemMessage(content=SYSTEM_PROMPT_TEMPLATE),
        HumanMessage(content=goal.model_dump_json(indent=2)),
    ]

    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response = await model.ainvoke(messages)
            parsed = _parse_llm_content(response.content)
            strategy = CampaignStrategy.model_validate(parsed)
            strategy = _apply_intent_defaults(strategy, goal)

            if len(strategy.target_audiences) < 2:
                raise ValueError("Strategy must include at least 2 personas")
            if len(strategy.target_audiences) > 3:
                raise ValueError("Strategy must include at most 3 personas")

            return {
                "agent_name": AGENT_NAME,
                "campaign_strategy": strategy.model_dump(),
                "planner_confidence": strategy.confidence_score,
            }
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            logger.warning(
                "Strategic planner attempt %s/%s failed: %s",
                attempt,
                max_retries,
                exc,
            )
            if attempt == max_retries:
                break
        except Exception as exc:  # defensive catch for provider/network errors
            last_error = exc
            logger.exception("Strategic planner provider error on attempt %s/%s", attempt, max_retries)
            if attempt == max_retries:
                break

    return {
        "agent_name": AGENT_NAME,
        "campaign_strategy": None,
        "planner_confidence": 0.0,
        "planner_error": str(last_error) if last_error else "Unknown planner error",
    }
