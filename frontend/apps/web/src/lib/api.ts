import { getValidAccessToken } from '@/lib/auth-session'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ENABLE_API_MOCKS = process.env.NEXT_PUBLIC_ENABLE_API_MOCKS === 'true' && process.env.NODE_ENV === 'test'

export type CampaignSummary = {
  campaign_id: string
  status: string
  current_agent?: string | null
  progress_percentage?: number
  estimated_completion?: string | null
  strategy?: Record<string, unknown> | null
  content?: { assets?: Array<Record<string, unknown>> } | null
  media_plan?: Record<string, unknown> | null
  performance?: { metrics?: Record<string, number>; anomalies?: Array<Record<string, unknown>> } | null
  report?: Record<string, unknown> | null
  pending_approval?: { type?: 'strategy' | 'media_plan' } | null
  error?: string | null
}

export type CampaignQASimulatePayload = {
  scenario:
    | 'content_zero_budget'
    | 'content_missing_audience'
    | 'media_low_budget_students'
    | 'media_high_budget'
    | 'media_invalid_budget'
    | 'performance_poor'
    | 'performance_excellent'
    | 'report_full'
  content_request?: string
  budget?: number
  audience?: string
  metrics?: {
    impressions: number
    clicks: number
    conversions: number
    spend: number
    revenue?: number
    unique_reach?: number
    objective?: string
    campaign_duration_days?: number
  }
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = await getValidAccessToken()

  // Campaign endpoints always require auth; never silently fallback to demo data here.
  if (path.startsWith('/api/v1/campaigns') && !token) {
    throw new Error('Missing bearer token. Please log in again.')
  }

  try {
    let res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options?.headers || {}),
      },
    })

    if (res.status === 401) {
      const retryToken = await getValidAccessToken()
      if (retryToken && retryToken !== token) {
        res = await fetch(`${API_URL}${path}`, {
          ...options,
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${retryToken}`,
            ...(options?.headers || {}),
          },
        })
      }
    }

    if (!res.ok) {
      let message = `API error (${res.status})`
      try {
        const body = await res.json()
        const topDetail = body?.error?.message ?? body?.detail ?? body?.message
        const fieldErrors: string[] = body?.error?.details
          ?.map((d: { loc?: string[]; msg?: string }) => {
            const field = d.loc?.slice(1).join('.') ?? 'field'
            return `${field}: ${d.msg}`
          })
          .filter(Boolean) ?? []
        if (fieldErrors.length > 0) {
          message = fieldErrors.join(' | ')
        } else if (topDetail) {
          message = typeof topDetail === 'string' ? topDetail : JSON.stringify(topDetail)
        }
      } catch {
        // ignore parse errors
      }
      throw new ApiError(message, res.status)
    }

    return (await res.json()) as T
  } catch (error) {
    const isNetworkError = error instanceof TypeError
    if (path.startsWith('/api/v1/auth') || path.startsWith('/api/v1/campaigns') || !ENABLE_API_MOCKS || !isNetworkError) {
      throw error
    }
    return mockResponse<T>(path, options)
  }
}

function mockResponse<T>(path: string, options?: RequestInit): T {
  const campaignId = 'demo-001'

  if (path === '/api/v1/campaigns' && options?.method === 'POST') {
    return { campaign_id: campaignId, status: 'running' } as T
  }

  if (path.startsWith('/api/v1/campaigns/') && options?.method === 'DELETE') {
    const id = path.split('/').pop() || campaignId
    return { campaign_id: id, message: 'Campaign deleted' } as T
  }

  if (path.endsWith('/status')) {
    return {
      campaign_id: campaignId,
      status: 'running',
      current_agent: 'content_creator',
      progress_percentage: 62,
      estimated_completion: new Date(Date.now() + 1000 * 60 * 8).toISOString(),
      error: null,
    } as T
  }

  if (path.endsWith('/content')) {
    return {
      assets: [
        {
          asset_id: 'ad-1',
          platform: 'google_ads',
          title: 'Scale Pipeline Faster',
          body: 'Launch optimized campaigns with autonomous planning.',
          variant: 'A',
        },
        {
          asset_id: 'ad-2',
          platform: 'google_ads',
          title: 'Boost Qualified Leads',
          body: 'Cut setup time and improve conversion rates.',
          variant: 'B',
        },
      ],
      count: 2,
    } as T
  }

  if (path.endsWith('/performance')) {
    return {
      metrics: { ctr: 0.024, cpc: 2.1, cpa: 58, roas: 3.1 },
      time_series: [
        { date: 'Mon', impressions: 12000, clicks: 330, conversions: 18 },
        { date: 'Tue', impressions: 14500, clicks: 410, conversions: 23 },
      ],
      anomalies: [{ metric: 'cpa', description: 'CPA spike detected on Meta segment' }],
    } as T
  }

  if (path.includes('/report')) {
    return {
      format: path.includes('markdown') ? 'markdown' : path.includes('pdf') ? 'pdf' : 'json',
      content: {
        executive_summary:
          'Campaign delivered above-target efficiency and stable conversion growth with actionable optimization learnings.',
      },
    } as T
  }

  if (path.includes('/api/v1/campaigns/')) {
    return {
      campaign_id: campaignId,
      status: 'running',
      current_agent: 'media_buyer',
      progress_percentage: 62,
      estimated_completion: new Date(Date.now() + 1000 * 60 * 8).toISOString(),
      strategy: {
        objectives: ['Increase qualified pipeline by 25% in 90 days'],
        confidence_score: 0.82,
        recommended_channels: [
          { channel: 'google_ads', budget_percentage: 50, rationale: 'High intent' },
          { channel: 'meta_ads', budget_percentage: 30, rationale: 'Retargeting scale' },
        ],
      },
      content: { assets: [{ asset_id: 'ad-1' }, { asset_id: 'ad-2' }] },
      media_plan: { channels: [{ channel: 'google_ads', budget: 50000 }] },
      performance: { metrics: { roas: 3.1 } },
      report: null,
      pending_approval: null,
      error: null,
    } as T
  }

  return {} as T
}

export async function createCampaign(payload: Record<string, unknown>) {
  return request<{ campaign_id: string; status: string }>('/api/v1/campaigns', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteCampaign(id: string) {
  return request<{ campaign_id: string; message: string }>(`/api/v1/campaigns/${id}`, {
    method: 'DELETE',
  })
}

export async function getCampaign(id: string) {
  return request<CampaignSummary>(`/api/v1/campaigns/${id}`)
}

export async function getCampaigns(limit: number = 50, offset: number = 0) {
  return request<{
    campaigns: Array<{
      campaign_id: string
      name: string | null
      status: string
      current_agent: string | null
      progress_percentage: number
      estimated_completion: string | null
      created_at: string
      updated_at: string
      budget_total?: number | null
      roi?: number | null
      pending_approval?: { type?: 'strategy' | 'media_plan' } | null
    }>
    total: number
  }>(`/api/v1/campaigns?limit=${limit}&offset=${offset}`)
}

export async function simulateCampaignQa(id: string, payload: CampaignQASimulatePayload) {
  return request<{ campaign_id: string; status: string; message: string }>(`/api/v1/campaigns/${id}/qa/simulate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getCampaignStatus(id: string) {
  return request<{
    campaign_id: string
    status: string
    current_agent: string | null
    progress_percentage: number
    estimated_completion: string | null
    error: string | null
  }>(`/api/v1/campaigns/${id}/status`)
}

export async function approveCampaign(id: string, payload: Record<string, unknown>) {
  return request<{ message: string }>(`/api/v1/campaigns/${id}/approve`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getCampaignContent(id: string) {
  return request<{ assets: Array<Record<string, unknown>>; count: number }>(`/api/v1/campaigns/${id}/content`)
}

export async function getCampaignPerformance(id: string) {
  return request<{ metrics: Record<string, number>; time_series: Array<Record<string, unknown>>; anomalies: Array<Record<string, unknown>> }>(
    `/api/v1/campaigns/${id}/performance`
  )
}

export async function getCampaignReport(id: string, format: 'json' | 'markdown' | 'pdf' = 'json') {
  return request<{ format: string; content: unknown; encoding?: string }>(`/api/v1/campaigns/${id}/report?format=${format}`)
}

export async function optimizeCampaign(id: string, payload: Record<string, unknown>) {
  return request<{ message: string }>(`/api/v1/campaigns/${id}/optimize`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
