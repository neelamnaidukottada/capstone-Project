'use client'

import React from 'react'
import { Dot } from 'lucide-react'
import { useUIStore } from '@/stores/ui-store'

export function WebSocketIndicator() {
  const status = useUIStore((s) => s.wsStatus)
  const color =
    status === 'connected'
      ? 'text-emerald-500'
      : status === 'connecting' || status === 'reconnecting'
        ? 'text-amber-500'
        : 'text-rose-500'

  const label =
    status === 'connected'
      ? 'Connected'
      : status === 'connecting'
        ? 'Connecting'
        : status === 'reconnecting'
          ? 'Reconnecting'
          : 'Disconnected'

  return (
    <div className="inline-flex items-center rounded-full border px-2 py-1 text-xs">
      <Dot className={color} />
      Realtime {label}
    </div>
  )
}
