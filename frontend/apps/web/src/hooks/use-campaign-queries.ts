'use client'

import { useQuery } from '@tanstack/react-query'
import { ApiError, getCampaign, getCampaignContent, getCampaignPerformance, getCampaignReport, getCampaignStatus } from '@/lib/api'

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
}

function isTerminalCampaignError(error: unknown): boolean {
  return error instanceof ApiError && [401, 403, 404].includes(error.status)
}

export function useCampaign(campaignId: string) {
  return useQuery({
    queryKey: ['campaign', campaignId],
    queryFn: () => getCampaign(campaignId),
    enabled: Boolean(campaignId) && isUuid(campaignId),
    retry: (failureCount, error) => !isTerminalCampaignError(error) && failureCount < 2,
    refetchInterval: (query) => (isTerminalCampaignError(query.state.error) ? false : 5000),
  })
}

export function useCampaignStatus(campaignId: string) {
  return useQuery({
    queryKey: ['campaign-status', campaignId],
    queryFn: () => getCampaignStatus(campaignId),
    enabled: Boolean(campaignId) && isUuid(campaignId),
    retry: (failureCount, error) => !isTerminalCampaignError(error) && failureCount < 2,
    refetchInterval: (query) => (isTerminalCampaignError(query.state.error) ? false : 3000),
  })
}

export function useCampaignContent(campaignId: string) {
  return useQuery({
    queryKey: ['campaign-content', campaignId],
    queryFn: () => getCampaignContent(campaignId),
    enabled: Boolean(campaignId) && isUuid(campaignId),
  })
}

export function useCampaignPerformance(campaignId: string) {
  return useQuery({
    queryKey: ['campaign-performance', campaignId],
    queryFn: () => getCampaignPerformance(campaignId),
    enabled: Boolean(campaignId) && isUuid(campaignId),
    refetchInterval: 5000,
  })
}

export function useCampaignReport(campaignId: string, format: 'json' | 'markdown' | 'pdf' = 'json') {
  return useQuery({
    queryKey: ['campaign-report', campaignId, format],
    queryFn: () => getCampaignReport(campaignId, format),
    enabled: Boolean(campaignId) && isUuid(campaignId),
  })
}
