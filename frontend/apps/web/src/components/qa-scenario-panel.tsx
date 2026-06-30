'use client'

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useToast } from '@/components/toaster'
import { simulateCampaignQa } from '@/lib/api'

type QAScenarioPanelProps = {
  campaignId: string
}

export function QAScenarioPanel({ campaignId }: QAScenarioPanelProps) {
  const isDebugEnabled = process.env.NEXT_PUBLIC_ENABLE_DEBUG === 'true'
  const { notify } = useToast()
  const queryClient = useQueryClient()

  const [customCtrPct, setCustomCtrPct] = useState(0.5)
  const [customConversions, setCustomConversions] = useState(2)
  const [customSpend, setCustomSpend] = useState(5000)
  const [customRevenue, setCustomRevenue] = useState(1000)
  const [contentRequest, setContentRequest] = useState('Create content for LinkedIn, Facebook, Email, and Google Ads.')

  const qaMutation = useMutation({
    mutationFn: async (payload: Parameters<typeof simulateCampaignQa>[1]) => simulateCampaignQa(campaignId, payload),
    onSuccess: (res) => {
      notify('QA scenario started', res.message)
      queryClient.invalidateQueries({ queryKey: ['campaign', campaignId] })
      queryClient.invalidateQueries({ queryKey: ['campaign-status', campaignId] })
      queryClient.invalidateQueries({ queryKey: ['campaign-content', campaignId] })
      queryClient.invalidateQueries({ queryKey: ['campaign-performance', campaignId] })
      queryClient.invalidateQueries({ queryKey: ['campaign-report', campaignId] })
    },
    onError: (error) => {
      notify('Unable to start QA scenario', error instanceof Error ? error.message : 'Please try again')
    },
  })

  if (!isDebugEnabled) return null

  const runCustomPerformance = () => {
    const clicks = Math.max(0, Math.round((customCtrPct / 100) * 1000))
    qaMutation.mutate({
      scenario: 'performance_poor',
      metrics: {
        impressions: 1000,
        clicks,
        conversions: Math.max(0, customConversions),
        spend: Math.max(0, customSpend),
        revenue: Math.max(0, customRevenue),
        unique_reach: 700,
        objective: 'conversion',
        campaign_duration_days: 30,
      },
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Dev QA Panel</CardTitle>
        <CardDescription>
          Development-only scenario runner for content, media buying, performance analyst, and report verification.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="space-y-2">
          <p className="text-sm font-medium">Content Request</p>
          <Textarea value={contentRequest} onChange={(e) => setContentRequest(e.target.value)} />
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              disabled={qaMutation.isPending}
              onClick={() => qaMutation.mutate({ scenario: 'content_zero_budget', content_request: contentRequest })}
            >
              Content Edge: Budget 0
            </Button>
            <Button
              variant="outline"
              disabled={qaMutation.isPending}
              onClick={() => qaMutation.mutate({ scenario: 'content_missing_audience', content_request: contentRequest })}
            >
              Content Edge: Missing Audience
            </Button>
          </div>
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium">Media Buying Scenarios</p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              disabled={qaMutation.isPending}
              onClick={() => qaMutation.mutate({ scenario: 'media_low_budget_students', content_request: contentRequest })}
            >
              Low Budget Students ($1000)
            </Button>
            <Button
              variant="outline"
              disabled={qaMutation.isPending}
              onClick={() => qaMutation.mutate({ scenario: 'media_high_budget', content_request: contentRequest })}
            >
              High Budget ($500000)
            </Button>
            <Button
              variant="outline"
              disabled={qaMutation.isPending}
              onClick={() => qaMutation.mutate({ scenario: 'media_invalid_budget', content_request: contentRequest })}
            >
              Invalid Budget (-$500)
            </Button>
          </div>
        </div>

        <div className="space-y-3">
          <p className="text-sm font-medium">Performance Analyst Scenarios</p>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
            <Input type="number" step="0.1" value={customCtrPct} onChange={(e) => setCustomCtrPct(Number(e.target.value) || 0)} placeholder="CTR %" />
            <Input type="number" value={customConversions} onChange={(e) => setCustomConversions(Number(e.target.value) || 0)} placeholder="Conversions" />
            <Input type="number" value={customSpend} onChange={(e) => setCustomSpend(Number(e.target.value) || 0)} placeholder="Spend" />
            <Input type="number" value={customRevenue} onChange={(e) => setCustomRevenue(Number(e.target.value) || 0)} placeholder="Revenue" />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={qaMutation.isPending} onClick={runCustomPerformance}>
              Run Custom Performance
            </Button>
            <Button variant="outline" disabled={qaMutation.isPending} onClick={() => qaMutation.mutate({ scenario: 'performance_poor' })}>
              Preset Poor Campaign
            </Button>
            <Button variant="outline" disabled={qaMutation.isPending} onClick={() => qaMutation.mutate({ scenario: 'performance_excellent' })}>
              Preset Excellent Campaign
            </Button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button disabled={qaMutation.isPending} onClick={() => qaMutation.mutate({ scenario: 'report_full', content_request: contentRequest })}>
            Generate Full Report Scenario
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
