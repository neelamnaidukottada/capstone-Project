import json
import pathlib
import sys

import pytest
from langchain_core.messages import AIMessage

# Allow importing packages/agents/src as a local module during tests.
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.planner import AGENT_NAME, strategic_planner_node


class FakeLLM:
    def __init__(self, responses):
        self._responses = responses
        self._idx = 0
        self.calls = []

    async def ainvoke(self, _messages):
        self.calls.append(_messages)
        response = self._responses[self._idx]
        self._idx += 1
        if isinstance(response, Exception):
            raise response
        return AIMessage(content=response)


@pytest.mark.asyncio
async def test_strategic_planner_node_successful_parse():
    mock_response = {
        "objectives": [
            "Increase qualified pipeline by 25% within 90 days.",
            "Reduce CAC by 15% before day 75.",
        ],
        "target_audiences": [
            {
                "name": "Ops Leader",
                "segment": "Mid-market ops",
                "demographics": ["Age 30-50", "US"],
                "pain_points": ["Manual reporting"],
                "motivations": ["Efficiency", "Predictability"],
            },
            {
                "name": "Revenue Manager",
                "segment": "Growth teams",
                "demographics": ["Age 28-45", "US/EU"],
                "pain_points": ["Rising CAC"],
                "motivations": ["Profitability", "Faster experiments"],
            },
        ],
        "key_messages": ["Automate execution", "Improve ROI"],
        "recommended_channels": [
            {
                "channel": "Paid Search",
                "budget_percentage": 40,
                "rationale": "High-intent buyers",
                "execution_notes": ["Brand + non-brand split"],
            },
            {
                "channel": "LinkedIn",
                "budget_percentage": 35,
                "rationale": "Decision-maker targeting",
                "execution_notes": ["ABM audiences"],
            },
            {
                "channel": "Email Nurture",
                "budget_percentage": 25,
                "rationale": "Conversion efficiency",
                "execution_notes": ["Persona drip campaigns"],
            },
        ],
        "timeline": [
            {
                "day": 1,
                "title": "Setup",
                "description": "Launch tracking and assets",
                "success_criteria": "Tracking validated",
            },
            {
                "day": 30,
                "title": "Optimize",
                "description": "Pause low performers",
                "success_criteria": "CPL improved 10%",
            },
            {
                "day": 75,
                "title": "Scale",
                "description": "Increase spend on winners",
                "success_criteria": "Pipeline growth trend positive",
            },
        ],
        "budget_allocation": {
            "Paid Search": 40000,
            "LinkedIn": 35000,
            "Email Nurture": 25000,
        },
        "competitive_differentiation": [
            "Faster onboarding than incumbent tools",
            "Transparent ROI dashboards",
        ],
        "confidence_score": 0.82,
    }

    llm = FakeLLM([json.dumps(mock_response)])

    result = await strategic_planner_node(
        state={
            "campaign_goal": {
                "goal": "Grow enterprise demo pipeline",
                "budget": 100000,
                "timeline_days": 90,
                "industry": "SaaS",
                "product_description": "AI platform for campaign automation and analytics",
            }
        },
        llm=llm,
    )

    assert result["agent_name"] == AGENT_NAME
    assert "planner_error" not in result
    assert result["campaign_strategy"]["confidence_score"] == pytest.approx(0.82)
    assert len(result["campaign_strategy"]["target_audiences"]) == 2


@pytest.mark.asyncio
async def test_strategic_planner_node_retries_and_returns_error_patch():
    invalid_payload = json.dumps(
        {
            "objectives": ["Objective 1"],
            "target_audiences": [],
            "key_messages": [],
            "recommended_channels": [],
            "timeline": [],
            "budget_allocation": {},
            "competitive_differentiation": [],
            "confidence_score": 0.2,
        }
    )

    llm = FakeLLM([invalid_payload, invalid_payload, invalid_payload])

    result = await strategic_planner_node(
        state={
            "campaign_goal": {
                "goal": "Increase retention",
                "budget": 20000,
                "timeline_days": 60,
                "industry": "D2C",
                "product_description": "Personalized skincare subscriptions",
            }
        },
        max_retries=3,
        llm=llm,
    )

    assert result["agent_name"] == AGENT_NAME
    assert result["campaign_strategy"] is None
    assert result["planner_confidence"] == 0.0
    assert "planner_error" in result


@pytest.mark.asyncio
async def test_strategic_planner_node_accepts_compact_brief_input():
    mock_response = {
        "objectives": [
            "Generate qualified signups for AI Resume Builder within 30 days.",
        ],
        "target_audiences": [
            {
                "name": "Early-Career Engineer",
                "segment": "Software Engineers",
                "demographics": ["Age 21-30"],
                "pain_points": ["Resume not passing ATS filters"],
                "motivations": ["Land interview calls faster"],
            },
            {
                "name": "Mid-Level Developer",
                "segment": "Software Engineers",
                "demographics": ["Age 28-40"],
                "pain_points": ["Resume lacks role-specific positioning"],
                "motivations": ["Move to higher-paying roles"],
            },
        ],
        "key_messages": [
            "Build a recruiter-ready resume with AI in minutes.",
            "Optimize your resume for software engineering roles.",
        ],
        "recommended_channels": [
            {
                "channel": "LinkedIn",
                "budget_percentage": 50,
                "rationale": "High concentration of software engineers.",
                "execution_notes": ["Target job titles and skills"],
            },
            {
                "channel": "GitHub Sponsorship",
                "budget_percentage": 50,
                "rationale": "Contextual reach with active developers.",
                "execution_notes": ["Run sponsored developer-focused placements"],
            },
        ],
        "timeline": [
            {
                "day": 1,
                "title": "Campaign kickoff",
                "description": "Finalize creatives and tracking",
                "success_criteria": "Tracking and landing page validated",
            },
            {
                "day": 15,
                "title": "Mid-flight optimization",
                "description": "Shift spend to best audience segments",
                "success_criteria": "CPC improves by 10%",
            },
            {
                "day": 30,
                "title": "Final push",
                "description": "Retarget high-intent visitors",
                "success_criteria": "Lead target achieved",
            },
        ],
        "budget_allocation": {
            "LinkedIn": 5000,
            "GitHub Sponsorship": 5000,
        },
        "competitive_differentiation": [
            "Resume suggestions tailored to software roles",
        ],
        "confidence_score": 0.84,
    }

    llm = FakeLLM([json.dumps(mock_response)])

    result = await strategic_planner_node(
        state={
            "campaign_goal": "Launch a campaign for our new AI Resume Builder.Budget: $10,000Duration: 30 daysTarget: Software Engineers"
        },
        llm=llm,
    )

    sent_goal = json.loads(llm.calls[0][1].content)

    assert sent_goal["budget"] == pytest.approx(10000)
    assert sent_goal["timeline_days"] == 30
    assert "Software Engineers" in sent_goal["product_description"]

    assert result["campaign_strategy"]["objectives"]
    assert result["campaign_strategy"]["target_audiences"]
    assert result["campaign_strategy"]["key_messages"]
    assert result["campaign_strategy"]["timeline"]


@pytest.mark.asyncio
async def test_strategic_planner_brand_awareness_defaults():
    mock_response = {
        "objectives": ["Increase unaided recall by 20% within 60 days."],
        "target_audiences": [
            {
                "name": "Awareness Persona A",
                "segment": "Broad prospecting",
                "demographics": ["Age 20-45"],
                "pain_points": ["Low familiarity"],
                "motivations": ["Discover trusted brands"],
            },
            {
                "name": "Awareness Persona B",
                "segment": "Social discovery",
                "demographics": ["Mobile-first users"],
                "pain_points": ["Message clutter"],
                "motivations": ["Clear brand promise"],
            },
        ],
        "key_messages": [
            "Trusted brand message for everyday decision making.",
        ],
        "recommended_channels": [
            {
                "channel": "YouTube",
                "budget_percentage": 40,
                "rationale": "High video reach.",
                "execution_notes": ["Frequency control"],
            }
        ],
        "timeline": [
            {
                "day": 1,
                "title": "Launch",
                "description": "Kickoff awareness campaign",
                "success_criteria": "Creative live",
            }
        ],
        "budget_allocation": {"YouTube": 10000},
        "competitive_differentiation": ["Clear category positioning"],
        "confidence_score": 0.8,
    }

    llm = FakeLLM([json.dumps(mock_response)])
    result = await strategic_planner_node(
        state={"campaign_goal": "Increase brand awareness for our company."},
        llm=llm,
    )

    strategy = result["campaign_strategy"]
    assert any("awareness" in objective.lower() for objective in strategy["objectives"])
    assert strategy["kpis"]
    channel_names = {channel["channel"].lower() for channel in strategy["recommended_channels"]}
    assert "instagram" in channel_names or "facebook" in channel_names or "linkedin" in channel_names


@pytest.mark.asyncio
async def test_strategic_planner_lead_generation_defaults():
    mock_response = {
        "objectives": ["Generate 500 B2B leads in 90 days."],
        "target_audiences": [
            {
                "name": "Ops Manager ICP",
                "segment": "B2B operations leaders",
                "demographics": ["Mid-market firms"],
                "pain_points": ["Low lead quality"],
                "motivations": ["Higher funnel efficiency"],
            },
            {
                "name": "Revenue Director",
                "segment": "Revenue leadership",
                "demographics": ["Director+"],
                "pain_points": ["Pipeline volatility"],
                "motivations": ["Predictable lead flow"],
            },
        ],
        "key_messages": ["Lead quality over quantity with measurable pipeline impact."],
        "recommended_channels": [
            {
                "channel": "LinkedIn",
                "budget_percentage": 60,
                "rationale": "B2B targeting precision.",
                "execution_notes": ["Lead forms"],
            }
        ],
        "timeline": [
            {
                "day": 1,
                "title": "Launch",
                "description": "Activate lead gen campaign",
                "success_criteria": "Tracking active",
            }
        ],
        "budget_allocation": {"LinkedIn": 12000},
        "competitive_differentiation": ["Faster follow-up workflow"],
        "confidence_score": 0.82,
    }

    llm = FakeLLM([json.dumps(mock_response)])
    result = await strategic_planner_node(
        state={"campaign_goal": "Generate 500 B2B leads."},
        llm=llm,
    )

    strategy = result["campaign_strategy"]
    assert strategy["target_audiences"]
    assert strategy["funnel_strategy"]
    assert strategy["lead_magnet_suggestions"]
