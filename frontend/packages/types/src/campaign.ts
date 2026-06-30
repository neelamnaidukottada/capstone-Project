// ── Campaign types ─────────────────────────────────────────────────────────

export type CampaignStatus = 'draft' | 'active' | 'paused' | 'completed' | 'failed'
export type CampaignChannel = 'email' | 'social' | 'paid_ads' | 'seo' | 'content'

export interface TargetAudience {
  ageRange?: { min: number; max: number }
  geographies?: string[]
  interests?: string[]
  industries?: string[]
  jobTitles?: string[]
  companySize?: string[]
}

export interface Campaign {
  id: string
  userId: string
  name: string
  description: string
  status: CampaignStatus
  channels: CampaignChannel[]
  budget: number
  targetAudience: TargetAudience
  goals: string[]
  createdAt: string
  updatedAt: string
}

export interface CreateCampaignInput {
  name: string
  description?: string
  channels: CampaignChannel[]
  budget: number
  targetAudience: TargetAudience
  goals: string[]
}

export interface UpdateCampaignInput {
  name?: string
  description?: string
  channels?: CampaignChannel[]
  budget?: number
  targetAudience?: Partial<TargetAudience>
  goals?: string[]
  status?: CampaignStatus
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}
