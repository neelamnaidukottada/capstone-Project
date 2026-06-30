'use client'

import { useEffect } from 'react'
import { io } from 'socket.io-client'
import { useUIStore } from '@/stores/ui-store'

type RealtimePayload = Record<string, unknown> | { event: 'raw'; payload: string }

export function useRealtimeIndicator() {
  const setWsConnected = useUIStore((s) => s.setWsConnected)

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
    const socket = io(base, {
      autoConnect: true,
      transports: ['websocket'],
      timeout: 2500,
      reconnection: true,
      reconnectionAttempts: 3,
    })

    socket.on('connect', () => setWsConnected(true))
    socket.on('disconnect', () => setWsConnected(false))
    socket.on('connect_error', () => setWsConnected(false))

    return () => {
      socket.disconnect()
      setWsConnected(false)
    }
  }, [setWsConnected])
}

export function useCampaignWebSocket(campaignId: string, onMessage: (payload: RealtimePayload) => void) {
  useEffect(() => {
    if (!campaignId) return

    const token = localStorage.getItem('acm-demo-token') ?? ''
    const base = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
    const wsUrl = base.replace('http://', 'ws://').replace('https://', 'wss://')
    const ws = new WebSocket(`${wsUrl}/ws/campaigns/${campaignId}?token=${token}`)

    ws.onmessage = (evt) => {
      try {
        onMessage(JSON.parse(evt.data))
      } catch {
        onMessage({ event: 'raw', payload: evt.data })
      }
    }

    return () => ws.close()
  }, [campaignId, onMessage])
}
