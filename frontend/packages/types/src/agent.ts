// ── Agent types ────────────────────────────────────────────────────────────

export type AgentStatus = 'idle' | 'running' | 'waiting' | 'completed' | 'failed'

export interface AgentRun {
  id: string
  campaignId: string
  status: AgentStatus
  threadId: string
  model: string
  createdAt: string
  completedAt: string | null
  error: string | null
}

export interface AgentEvent {
  id: string
  runId: string
  eventType: AgentEventType
  payload: Record<string, unknown>
  createdAt: string
}

export type AgentEventType =
  | 'tool_call'
  | 'tool_result'
  | 'message'
  | 'checkpoint'
  | 'error'
  | 'complete'

export interface StartAgentRunInput {
  campaignId: string
  instructions?: string
  model?: string
  temperature?: number
}

// SSE event envelope sent over /agents/runs/:id/stream
export interface AgentStreamEvent {
  runId: string
  eventType: AgentEventType
  data: Record<string, unknown>
  timestamp: string
}
