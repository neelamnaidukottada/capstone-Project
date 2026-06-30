'use client'

import * as Toast from '@radix-ui/react-toast'
import { createContext, useContext, useMemo, useState } from 'react'

type ToastMessage = { id: string; title: string; description?: string }

type ToastContextType = {
  notify: (title: string, description?: string) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [messages, setMessages] = useState<ToastMessage[]>([])

  const notify = (title: string, description?: string) => {
    const id = typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : String(Date.now())
    setMessages((prev) => [...prev, { id, title, description }])
    setTimeout(() => {
      setMessages((prev) => prev.filter((m) => m.id !== id))
    }, 2500)
  }

  const value = useMemo(() => ({ notify }), [])

  return (
    <ToastContext.Provider value={value}>
      <Toast.Provider swipeDirection="right">
        {children}
        {messages.map((msg) => (
          <Toast.Root key={msg.id} className="fixed bottom-4 right-4 z-50 w-[320px] rounded-lg border bg-card p-4 shadow-lg">
            <Toast.Title className="font-semibold">{msg.title}</Toast.Title>
            {msg.description ? (
              <Toast.Description className="text-sm text-muted-foreground">{msg.description}</Toast.Description>
            ) : null}
          </Toast.Root>
        ))}
        <Toast.Viewport className="fixed bottom-0 right-0 z-[100] m-0 flex max-h-screen w-[390px] list-none flex-col gap-2 p-4 outline-none" />
      </Toast.Provider>
    </ToastContext.Provider>
  )
}
