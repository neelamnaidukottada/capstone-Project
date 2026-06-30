import { create } from 'zustand'

type RealtimeEvent = {
  id: string
  agent: string
  status: string
  message: string
  timestamp: string
}

type CampaignLocalState = {
  activeCampaignId: string | null
  approvalModalOpen: boolean
  approvalType: 'strategy' | 'media_plan' | null
  realtimeEvents: RealtimeEvent[]
  websocketError: string | null
  setActiveCampaignId: (id: string | null) => void
  openApprovalModal: (type: 'strategy' | 'media_plan') => void
  closeApprovalModal: () => void
  addRealtimeEvent: (event: RealtimeEvent) => void
  clearRealtimeEvents: () => void
  setWebsocketError: (error: string | null) => void
}

export const useCampaignStore = create<CampaignLocalState>((set) => ({
  activeCampaignId: null,
  approvalModalOpen: false,
  approvalType: null,
  realtimeEvents: [],
  websocketError: null,
  setActiveCampaignId: (activeCampaignId) => set({ activeCampaignId }),
  openApprovalModal: (approvalType) => set({ approvalType, approvalModalOpen: true }),
  closeApprovalModal: () => set({ approvalModalOpen: false, approvalType: null }),
  addRealtimeEvent: (event) =>
    set((state) => ({ realtimeEvents: [event, ...state.realtimeEvents].slice(0, 50) })),
  clearRealtimeEvents: () => set({ realtimeEvents: [] }),
  setWebsocketError: (websocketError) => set({ websocketError }),
}))
