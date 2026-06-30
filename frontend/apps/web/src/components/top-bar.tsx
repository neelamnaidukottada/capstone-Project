'use client'

import { Bell, UserCircle2 } from 'lucide-react'
import { useAuth } from '@/components/auth-provider'
import { ThemeToggle } from '@/components/theme-toggle'
import { WebSocketIndicator } from '@/components/ws-indicator'

export function TopBar() {
  const { user, logout } = useAuth()

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b bg-background/95 px-4 backdrop-blur">
      <div>
        <p className="text-sm text-muted-foreground">Autonomous Campaign Manager</p>
        <h1 className="text-lg font-semibold">Control Center</h1>
      </div>

      <div className="flex items-center gap-3">
        <WebSocketIndicator />
        <button className="rounded-md border p-2" aria-label="Notifications">
          <Bell className="h-4 w-4" />
        </button>
        <ThemeToggle />
        <button
          className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm"
          onClick={() => {
            void logout()
          }}
        >
          <UserCircle2 className="h-4 w-4" />
          {user?.full_name || user?.email || 'Account'}
        </button>
      </div>
    </header>
  )
}
