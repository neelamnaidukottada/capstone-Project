'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useToast } from '@/components/toaster'
import { getValidAccessToken } from '@/lib/auth-session'
import websocketContractJson from '@/lib/websocket-contract.json'
import { useCampaignStore } from '@/stores/campaign-store'
import { useUIStore, type WebSocketStatus } from '@/stores/ui-store'

export type AgentStartedEvent = {
  event: 'agent_started'
  timestamp: string
  agent_name: string
  input_summary: string
}

export type AgentCompletedEvent = {
  event: 'agent_completed'
  timestamp: string
  agent_name: string
  output_summary: string
  latency: number
}

export type HumanApprovalRequiredEvent = {
  event: 'human_approval_required'
  timestamp: string
  step: string
  payload: Record<string, unknown>
  timeout: number
}

export type OptimizationAlertEvent = {
  event: 'optimization_alert'
  timestamp: string
  severity: string
  message: string
  recommendation: string
}

export type CampaignCompletedEvent = {
  event: 'campaign_completed'
  timestamp: string
  campaign_id: string
  report_url: string
}

export type AgentErrorEvent = {
  event: 'error'
  timestamp: string
  agent_name: string
  error_message: string
  retry_count: number
}

export type PingEvent = { event: 'ping'; timestamp: string }
export type PongEvent = { event: 'pong'; timestamp: string }
export type ConnectedEvent = { event: 'connected'; timestamp: string; campaign_id: string; message: string }

export type CampaignSocketEvent =
  | AgentStartedEvent
  | AgentCompletedEvent
  | HumanApprovalRequiredEvent
  | OptimizationAlertEvent
  | CampaignCompletedEvent
  | AgentErrorEvent
  | PingEvent
  | PongEvent
  | ConnectedEvent

const websocketContract = websocketContractJson as Record<string, readonly string[]>

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function hasRequiredKeys(payload: Record<string, unknown>, keys: readonly string[]): boolean {
  return keys.every((key) => key in payload)
}

export function parseCampaignSocketEvent(raw: string): CampaignSocketEvent | null {
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!isObject(parsed)) {
      return null
    }

    const eventName = parsed.event
    if (typeof eventName !== 'string') {
      return null
    }

    const requiredKeys = websocketContract[eventName]
    if (!requiredKeys || !hasRequiredKeys(parsed, requiredKeys)) {
      return null
    }

    return parsed as CampaignSocketEvent
  } catch {
    return null
  }
}

export function useCampaignWebSocket(campaignId: string) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptRef = useRef(0)
  const intentionallyClosedRef = useRef(false)

  const [status, setStatus] = useState<WebSocketStatus>('disconnected')
  const [lastEvent, setLastEvent] = useState<CampaignSocketEvent | null>(null)
  const [error, setError] = useState<string | null>(null)

  const setWsStatus = useUIStore((s) => s.setWsStatus)
  const addRealtimeEvent = useCampaignStore((s) => s.addRealtimeEvent)
  const setWebsocketError = useCampaignStore((s) => s.setWebsocketError)
  const setActiveCampaignId = useCampaignStore((s) => s.setActiveCampaignId)

  const queryClient = useQueryClient()
  const { notify } = useToast()

  const updateStatus = useCallback(
    (next: WebSocketStatus) => {
      setStatus(next)
      setWsStatus(next)
    },
    [setWsStatus]
  )

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
  }, [])

  const connect = useCallback(() => {
    const open = async () => {
      if (!campaignId) return

      setActiveCampaignId(campaignId)
      updateStatus(reconnectAttemptRef.current > 0 ? 'reconnecting' : 'connecting')

      const token = (await getValidAccessToken()) ?? ''
      const base = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
      const wsUrl = base.replace('http://', 'ws://').replace('https://', 'wss://')

      const ws = new WebSocket(`${wsUrl}/ws/campaigns/${campaignId}?token=${token}`)
      wsRef.current = ws

      ws.onopen = () => {
        reconnectAttemptRef.current = 0
        setError(null)
        setWebsocketError(null)
        updateStatus('connected')
      }

      ws.onerror = () => {
        const msg = 'WebSocket connection failed'
        setError(msg)
        setWebsocketError(msg)
      }

      ws.onclose = (event) => {
        wsRef.current = null

        if (intentionallyClosedRef.current) {
          updateStatus('disconnected')
          return
        }

        if ([4401, 4403, 4404].includes(event.code)) {
          const msg =
            event.code === 4404
              ? 'Campaign not found'
              : event.code === 4403
                ? 'Access denied for this campaign'
                : 'Authentication required for campaign stream'
          setError(msg)
          setWebsocketError(msg)
          updateStatus('disconnected')
          return
        }

        updateStatus('reconnecting')
        const attempt = reconnectAttemptRef.current + 1
        reconnectAttemptRef.current = attempt
        const backoffMs = Math.min(30000, 1000 * 2 ** Math.min(attempt, 6))

        reconnectTimerRef.current = setTimeout(() => {
          connect()
        }, backoffMs)
      }

      ws.onmessage = (evt) => {
        const payload = parseCampaignSocketEvent(evt.data)

        if (!payload) return
        setLastEvent(payload)

        if (payload.event === 'ping') {
          ws.send(JSON.stringify({ type: 'pong', timestamp: new Date().toISOString() }))
          return
        }

        if (payload.event === 'pong' || payload.event === 'connected') {
          return
        }

        addRealtimeEvent({
          id: typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : String(Date.now()),
          agent: 'agent_name' in payload ? payload.agent_name : 'supervisor',
          status: payload.event,
          message:
            payload.event === 'agent_started'
              ? payload.input_summary
              : payload.event === 'agent_completed'
                ? payload.output_summary
                : payload.event === 'human_approval_required'
                  ? `Approval needed: ${payload.step}`
                  : payload.event === 'optimization_alert'
                    ? payload.message
                    : payload.event === 'campaign_completed'
                      ? 'Campaign workflow completed'
                      : payload.event === 'error'
                        ? payload.error_message
                        : 'Workflow update',
          timestamp: new Date(payload.timestamp).toLocaleTimeString(),
        })

        if (payload.event === 'human_approval_required') {
          notify('Human approval required', `Step: ${payload.step}`)
        }
        if (payload.event === 'optimization_alert' && ['high', 'critical'].includes(payload.severity.toLowerCase())) {
          notify('Optimization alert', payload.recommendation)
        }
        if (payload.event === 'campaign_completed') {
          notify('Campaign completed', 'Final report is ready')
        }
        if (payload.event === 'error') {
          notify('Workflow error', `${payload.agent_name}: ${payload.error_message}`)
        }

        queryClient.invalidateQueries({ queryKey: ['campaign', campaignId] })
        queryClient.invalidateQueries({ queryKey: ['campaign-status', campaignId] })
        queryClient.invalidateQueries({ queryKey: ['campaign-performance', campaignId] })
        queryClient.invalidateQueries({ queryKey: ['campaign-content', campaignId] })
        queryClient.invalidateQueries({ queryKey: ['campaign-report', campaignId] })
      }
    }

    void open()
  }, [
    addRealtimeEvent,
    campaignId,
    notify,
    queryClient,
    setActiveCampaignId,
    setWebsocketError,
    updateStatus,
  ])

  useEffect(() => {
    if (!isUuid(campaignId)) {
      setError('Invalid campaign id')
      setWebsocketError('Invalid campaign id')
      updateStatus('disconnected')
      return
    }

    intentionallyClosedRef.current = false
    connect()

    return () => {
      intentionallyClosedRef.current = true
      clearReconnectTimer()
      wsRef.current?.close()
      wsRef.current = null
      updateStatus('disconnected')
    }
  }, [campaignId, clearReconnectTimer, connect, updateStatus])

  return {
    status,
    lastEvent,
    reconnectAttempt: reconnectAttemptRef.current,
    error,
  }
}
