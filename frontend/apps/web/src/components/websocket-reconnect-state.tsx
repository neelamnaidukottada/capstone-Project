'use client'

import React from 'react'
import { useUIStore } from '@/stores/ui-store'

export function WebSocketReconnectState() {
  const status = useUIStore((s) => s.wsStatus)

  if (status === 'connected') {
    return null
  }

  return (
    <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
      {status === 'connecting' && 'Connecting to campaign realtime channel...'}
      {status === 'reconnecting' && 'Connection dropped. Reconnecting with backoff...'}
      {status === 'disconnected' && 'Realtime updates disconnected.'}
    </div>
  )
}
