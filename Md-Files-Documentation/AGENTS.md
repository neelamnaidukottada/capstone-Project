# Agent Specifications & Implementation

## Overview

The Autonomous Campaign Manager orchestrates five specialized AI agents in a LangGraph workflow. Each agent has:
- **Input Contract**: Well-defined input schema
- **Output Contract**: Structured output format
- **Failure Modes**: Known error cases and fallbacks
- **Constraints**: Guardrails and business rules

## 1. Planner Agent

### Purpose
Generates a comprehensive campaign strategy from a brief, establishing positioning, channel allocation, KPI targets, and timeline.

### Input Contract

```python
class PlannerInput(BaseModel):
    campaign_name: str
    business_goal: str
    target_audience: str
    budget_total: float
    channels: List[str]  # e.g., ["email", "social_media", "influencer"]
    start_date: str  # ISO-8601
    end_date: str    # ISO-8601
    constraints: Optional[Dict[str, Any]] = None
```

### Output Contract

```python
class ChannelPlan(BaseModel):
    channel: str
    rationale: str
    target_reach: int
    estimated_engagement_rate: float

class Strategy(BaseModel):
    campaign_id: str
    positioning_statement: str
    channel_plans: List[ChannelPlan]
    kpi_targets: Dict[str, float]  # e.g., {"impressions": 100000, "ctr": 0.08}
    timeline: Dict[str, str]  # e.g., {"week_1": "launch", "week_2": "optimize"}
    key_messages: List[str]
    risks_and_mitigations: List[Dict[str, str]]
```

### Example

```python
# Planner Input
{
  "campaign_name": "Summer Sale 2026",
  "business_goal": "Drive 50% increase in online sales",
  "target_audience": "Women 25-45, interested in fashion, urban areas",
  "budget_total": 10000,
  "channels": ["instagram", "email", "tiktok"],
  "start_date": "2026-07-01",
  "end_date": "2026-07-31"
}

# Planner Output (Summary)
{
  "positioning_statement": "Summer Sale 2026 positions our brand as the go-to destination for women seeking stylish, affordable fashion.",
  "channel_plans": [
    {
      "channel": "instagram",
      "rationale": "High engagement with target demographic",
      "target_reach": 50000,
      "estimated_engagement_rate": 0.08
    },
    ...
  ],
  "kpi_targets": {
    "impressions": 250000,
    "clicks": 15000,
    "conversions": 1500,
    "revenue": 75000
  }
}
```

### Failure Modes

| Error | Cause | Fallback |
|-------|-------|----------|
| **Ambiguous Goal** | Business goal too vague | Request clarification, suggest goal templates |
| **Invalid Budget** | Budget insufficient for channels | Recommend reducing channels or extending timeline |
| **Unsupported Channel** | Channel not in provider list | Map to supported alternative |
| **Date Range Invalid** | End date before start date | Auto-correct with warning |

### Implementation

```python
# backend/packages/agents/src/planner.py
from langgraph.graph import StateGraph
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

class PlannerAgent:
    def __init__(self, llm_model="gpt-4"):
        self.llm = ChatOpenAI(model=llm_model, temperature=0.7)
    
    async def plan(self, brief: PlannerInput) -> Strategy:
        """Generate campaign strategy from brief"""
        
        # Validate input
        try:
            validated_brief = PlannerInput(**brief)
        except ValidationError as e:
            raise ValueError(f"Invalid brief: {e}")
        
        # Construct prompt
        prompt = self._build_strategy_prompt(validated_brief)
        
        # Call LLM
        response = await self.llm.ainvoke(prompt)
        
        # Parse and validate output
        strategy = self._parse_response(response.content)
        
        return strategy
    
    def _build_strategy_prompt(self, brief: PlannerInput) -> str:
        return f"""
        You are a campaign strategist. Generate a comprehensive campaign strategy.
        
        Campaign: {brief.campaign_name}
        Goal: {brief.business_goal}
        Audience: {brief.target_audience}
        Budget: ${brief.budget_total}
        Channels: {', '.join(brief.channels)}
        Timeline: {brief.start_date} to {brief.end_date}
        
        Provide a JSON response with:
        - positioning_statement
        - channel_plans (array with channel, rationale, target_reach, engagement_rate)
        - kpi_targets (object with metric: target)
        - timeline (object with phase: activity)
        - key_messages (array)
        - risks_and_mitigations (array)
        """
```

## 2. Content Creator Agent

### Purpose
Generates creative asset drafts including copy variants, hooks, CTAs, and format metadata based on planner strategy.

### Input Contract

```python
class ContentCreatorInput(BaseModel):
    campaign_id: str
    strategy: Strategy  # From Planner
    brand_guidelines: Optional[Dict[str, Any]] = None
    format_preferences: Optional[List[str]] = None  # e.g., ["carousel", "video", "text"]
```

### Output Contract

```python
class CreativeAsset(BaseModel):
    id: str
    format: str  # "carousel_post", "email_subject", "video_script", etc.
    channel: str
    copy_variants: List[str]  # Multiple copy options
    hooks: List[str]  # Opening lines
    cta: str  # Call-to-action
    asset_metadata: Dict[str, Any]  # Dimensions, duration, etc.
    performance_prediction: Dict[str, float]

class ContentOutput(BaseModel):
    campaign_id: str
    assets: List[CreativeAsset]
    brand_alignment_score: float  # 0-1, how well aligned with guidelines
    recommendations: List[str]
```

### Failure Modes

| Error | Cause | Fallback |
|-------|-------|----------|
| **Brand Violation** | Generated content misaligned with brand | Regenerate with stricter constraints |
| **Format Mismatch** | Format not optimal for channel | Adjust format recommendations |
| **Low Originality** | Copy too generic | Request higher creativity level |

## 3. Media Buyer Agent

### Purpose
Determines budget allocation by channel, pacing strategy, and spend rationale based on strategy and available budget.

### Input Contract

```python
class MediaBuyerInput(BaseModel):
    campaign_id: str
    strategy: Strategy
    total_budget: float
    channel_preferences: Optional[Dict[str, float]] = None  # min/max per channel
    pacing_strategy: str = "even"  # "even", "front_loaded", "back_loaded"
```

### Output Contract

```python
class ChannelAllocation(BaseModel):
    channel: str
    allocated_budget: float
    daily_spend: float
    spend_rationale: str
    expected_cpm: float
    expected_reach: int

class MediaPlan(BaseModel):
    campaign_id: str
    total_budget: float
    allocations: List[ChannelAllocation]
    pacing_schedule: Dict[str, float]  # day: budget for that day
    contingency_reserve: float  # % of budget held back
    roi_projection: float  # Expected ROI %
```

### Example

```python
# Media Buyer Output
{
  "allocations": [
    {
      "channel": "instagram",
      "allocated_budget": 5000,
      "daily_spend": 160.71,
      "spend_rationale": "Highest engagement rate with target demographic",
      "expected_cpm": 5.50,
      "expected_reach": 909090
    },
    {
      "channel": "email",
      "allocated_budget": 3000,
      "daily_spend": 96.77,
      "expected_cpm": 0.50,
      "expected_reach": 6000000
    },
    {
      "channel": "tiktok",
      "allocated_budget": 2000,
      "daily_spend": 64.52,
      "expected_cpm": 2.00,
      "expected_reach": 1000000
    }
  ],
  "contingency_reserve": 500,
  "roi_projection": 8.5
}
```

### Failure Modes

| Error | Cause | Fallback |
|-------|-------|----------|
| **Over-allocation** | Allocations exceed budget | Normalize all allocations proportionally |
| **CPM Mismatch** | Channel CPM outdated | Use historical average |
| **Invalid Pacing** | Pacing strategy not recognized | Default to "even" distribution |

## 4. Performance Analyst Agent

### Purpose
Analyzes run metrics and historical data to provide performance insights, anomalies, and optimization suggestions.

### Input Contract

```python
class PerformanceAnalystInput(BaseModel):
    campaign_id: str
    run_id: str
    media_plan: MediaPlan  # From Media Buyer
    historical_campaigns: Optional[List[Dict[str, Any]]] = None
    current_metrics: Optional[Dict[str, float]] = None  # If mid-campaign
```

### Output Contract

```python
class PerformanceInsight(BaseModel):
    metric: str
    actual_value: float
    target_value: float
    variance_percent: float
    status: str  # "on_track", "warning", "critical"
    recommendation: str

class AnalysisOutput(BaseModel):
    campaign_id: str
    insights: List[PerformanceInsight]
    anomalies: List[Dict[str, Any]]
    optimization_suggestions: List[str]
    confidence_level: float  # 0-1, based on data availability
    next_review_date: str
```

### Failure Modes

| Error | Cause | Fallback |
|-------|-------|----------|
| **Sparse Data** | Insufficient historical data | Flag with low confidence, use benchmarks |
| **Anomaly Not Explainable** | Unusual pattern but no clear cause | Note anomaly with unknown cause |
| **Model Unavailable** | ML model for predictions down | Use rule-based heuristics |

## 5. Reporter Agent

### Purpose
Compiles all prior stage outputs, metrics, and insights into a comprehensive, executive-ready report.

### Input Contract

```python
class ReporterInput(BaseModel):
    campaign_id: str
    run_id: str
    strategy: Strategy
    content: ContentOutput
    media_plan: MediaPlan
    analysis: AnalysisOutput
    final_metrics: Optional[Dict[str, float]] = None
```

### Output Contract

```python
class ReportSection(BaseModel):
    title: str
    content: str  # Markdown
    visualizations: Optional[List[str]] = None

class ReportBundle(BaseModel):
    campaign_id: str
    run_id: str
    summary: str  # Executive summary (200-300 words)
    sections: List[ReportSection]
    recommendations: List[str]
    key_metrics: Dict[str, float]
    export_formats: List[str] = ["json", "markdown"]
```

### Report Sections

1. **Executive Summary** - High-level overview for decision makers
2. **Campaign Overview** - Goals, budget, timeline
3. **Strategy** - Positioning and channel approach
4. **Creative Assets** - Generated content overview
5. **Media Plan** - Budget allocation and pacing
6. **Performance Analysis** - Insights and anomalies
7. **Recommendations** - Next steps and optimizations
8. **Appendix** - Detailed metrics tables

### Failure Modes

| Error | Cause | Fallback |
|-------|-------|----------|
| **Missing Section** | Upstream agent failed | Use template with "N/A" and note |
| **Export Format Error** | PDF generation failed | Provide JSON/Markdown only |
| **Token Limit** | Report too large for model | Summarize sections, trim details |

## 6. Orchestrator

### Purpose
Controls execution graph, manages state transitions, enforces approval gates, handles retries, and orchestrates completion.

### Graph Flow

```
START
  ↓
[PLANNER] → strategy_completed event
  ↓
[GATE: Strategy Approval]
  ├─ Approved → continue
  └─ Rejected → ROLLBACK to START
  ↓
[CONTENT_CREATOR] → content_completed event
  ↓
[MEDIA_BUYER] → media_plan_completed event
  ↓
[GATE: Budget Approval]
  ├─ Approved → continue
  └─ Rejected → ROLLBACK to CONTENT_CREATOR
  ↓
[PERFORMANCE_ANALYST] → analysis_completed event
  ↓
[REPORTER] → report_completed event
  ↓
COMPLETION → workflow_completed event
  ↓
END
```

### State Management

```python
class OrchestrationState(BaseModel):
    campaign_id: str
    run_id: str
    current_stage: str
    strategy: Optional[Strategy] = None
    content: Optional[ContentOutput] = None
    media_plan: Optional[MediaPlan] = None
    analysis: Optional[AnalysisOutput] = None
    report: Optional[ReportBundle] = None
    approval_gates: Dict[str, bool] = {}  # gate_name: approved
    events: List[Dict[str, Any]] = []
    errors: List[str] = []
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

### Gate Control

```python
class ApprovalGate(BaseModel):
    gate_name: str  # "strategy", "budget"
    required_for_stage: str  # What stage does this gate protect
    payload: Dict[str, Any]  # Content for human review
    created_at: datetime
    approved: Optional[bool] = None
    reviewer_id: Optional[str] = None
    decided_at: Optional[datetime] = None

async def handle_approval(gate_name: str, approved: bool) -> None:
    """
    Process approval decision and resume/rollback workflow
    """
    if approved:
        # Resume from next stage
        await resume_workflow()
    else:
        # Rollback or terminate
        await rollback_to_previous_stage()
```

## Implementation Patterns

### Agent Node Pattern (Correct)

```python
# ✅ CORRECT: Async function directly
async def planner_node(state: OrchestrationState) -> OrchestrationState:
    """LangGraph node for planner agent"""
    agent = PlannerAgent()
    strategy = await agent.plan(state.campaign_brief)
    
    # Update state
    state.strategy = strategy
    state.current_stage = "strategy_completed"
    
    # Emit event
    await emit_event(
        campaign_id=state.campaign_id,
        event_type="agent_completed",
        agent_name="planner",
        payload=strategy.dict()
    )
    
    return state

# ❌ WRONG: Lambda wrapping async (returns coroutine)
def planner_node_wrong(state):
    return lambda: PlannerAgent().plan(...)  # WRONG!
```

### Error Handling Pattern

```python
async def agent_node_with_retry(state: OrchestrationState, agent_name: str) -> OrchestrationState:
    """Agent node with built-in retry and error handling"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            agent = get_agent(agent_name)
            result = await agent.process(state)
            return result
        except ValueError as e:
            if "rate_limit" in str(e):
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                retry_count += 1
            else:
                # Unrecoverable error
                state.errors.append(f"{agent_name}: {str(e)}")
                return state
        except Exception as e:
            state.errors.append(f"{agent_name}: Unexpected error: {str(e)}")
            return state
    
    state.errors.append(f"{agent_name}: Max retries exceeded")
    return state
```

### Testing Agent Nodes

```python
@pytest.mark.asyncio
async def test_planner_node():
    """Test planner node in isolation"""
    state = OrchestrationState(
        campaign_id="test-id",
        campaign_brief={...}
    )
    
    result = await planner_node(state)
    
    assert result.strategy is not None
    assert result.current_stage == "strategy_completed"
    assert len(result.events) > 0
```

---

**Related Documentation**:
- [SPEC.md](SPEC.md) - Contract definitions
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [TESTING.md](TESTING.md) - Agent testing
