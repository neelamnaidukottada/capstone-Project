import { create } from 'zustand'

export type WebSocketStatus = 'connected' | 'connecting' | 'reconnecting' | 'disconnected'

type UIState = {
  theme: 'light' | 'dark'
  wsConnected: boolean
  wsStatus: WebSocketStatus
  setTheme: (theme: 'light' | 'dark') => void
  setWsConnected: (connected: boolean) => void
  setWsStatus: (status: WebSocketStatus) => void
}

export const useUIStore = create<UIState>((set) => ({
  theme: 'light',
  wsConnected: false,
  wsStatus: 'disconnected',
  setTheme: (theme) => set({ theme }),
  setWsConnected: (wsConnected) => set({ wsConnected }),
  setWsStatus: (wsStatus) => set({ wsStatus, wsConnected: wsStatus === 'connected' }),
}))
