'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Download, Edit3, ThumbsDown, ThumbsUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { useToast } from '@/components/toaster'
import { useCampaign } from '@/hooks/use-campaign-queries'
import { approveCampaign } from '@/lib/api'

type StrategyChannel = {
  channel: string
  rationale?: string
  budget_percentage?: number
}

type CampaignStrategy = {
  confidence_score?: number
  objectives?: string[]
  kpis?: string[]
  funnel_strategy?: string[]
  lead_magnet_suggestions?: string[]
  recommended_channels?: StrategyChannel[]
}

export default function CampaignStrategyPage() {
  const { id } = useParams<{ id: string }>()
  const campaignId = Array.isArray(id) ? id[0] : id
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const [isRequestingEdits, setIsRequestingEdits] = useState(false)
  const { data } = useCampaign(campaignId)
  const strategy = (data?.strategy as CampaignStrategy | null | undefined) ?? null
  const confidence = Number(strategy?.confidence_score ?? 0) * 100
  const objectives = strategy?.objectives ?? []
  const kpis = strategy?.kpis ?? []
  const funnelStrategy = strategy?.funnel_strategy ?? []
  const leadMagnets = strategy?.lead_magnet_suggestions ?? []
  const channels = strategy?.recommended_channels ?? []
  const workflowError = data?.error
  const strategyApprovalPending = data?.pending_approval?.type === 'strategy'

  const approvalMutation = useMutation({
    mutationFn: async ({ approved, feedback }: { approved: boolean; feedback: string }) =>
      approveCampaign(campaignId, {
        approval_type: 'strategy',
        approved,
        feedback,
      }),
    onSuccess: (_, variables) => {
      if (variables.approved) {
        notify('Strategy approved', 'Workflow resumed with approved strategy')
      } else {
        notify('Feedback sent', 'Strategy revision request submitted')
      }
      queryClient.invalidateQueries({ queryKey: ['campaign', campaignId] })
      queryClient.invalidateQueries({ queryKey: ['campaign-status', campaignId] })
    },
  })

  const handleApprove = () => {
    if (!strategyApprovalPending) {
      notify('No strategy approval pending', 'Approval controls are active only when the workflow is waiting for strategy review')
      return
    }
    approvalMutation.mutate({ approved: true, feedback: '' })
  }

  const handleReject = () => {
    if (!strategyApprovalPending) {
      notify('No strategy approval pending', 'Use this action when strategy review is requested by the workflow')
      return
    }
    const feedback = window.prompt('Provide rejection feedback for the strategy:')
    if (feedback === null) return
    approvalMutation.mutate({
      approved: false,
      feedback: feedback.trim() || 'Rejected from strategy page without additional details.',
    })
  }

  const handleEditStrategy = () => {
    if (!strategyApprovalPending) {
      notify('No strategy approval pending', 'Edit requests are submitted through strategy rejection feedback during review')
      return
    }
    setIsRequestingEdits(true)
    const feedback = window.prompt('What should the planner change in the strategy?', 'Please revise targeting and channel mix.')
    setIsRequestingEdits(false)
    if (feedback === null) return
    approvalMutation.mutate({
      approved: false,
      feedback: `Edit request: ${feedback.trim() || 'Please revise the strategy.'}`,
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Strategy</h2>
        <Button variant="outline" className="gap-2">
          <Download className="h-4 w-4" />
          Export PDF
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Confidence Score</CardTitle>
          <CardDescription>Planner confidence for generated strategy.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <Progress value={confidence} />
          <p className="text-sm text-muted-foreground">{confidence.toFixed(0)}%</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Objectives</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {objectives.length ? objectives.map((objective: string) => (
            <p key={objective} className="rounded-md border p-3 text-sm">
              {objective}
            </p>
          )) : <p className="rounded-md border p-3 text-sm text-muted-foreground">Strategy is still generating.</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recommended Channels</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {channels.length ? channels.map((channel) => (
            <div key={channel.channel} className="rounded-lg border p-4">
              <p className="font-medium">{channel.channel}</p>
              <p className="text-sm text-muted-foreground">{channel.rationale}</p>
              <p className="mt-2 text-sm">Budget: {channel.budget_percentage}%</p>
            </div>
          )) : <p className="text-sm text-muted-foreground">Channel recommendations will appear when planning completes.</p>}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Awareness KPIs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {kpis.length ? kpis.map((kpi) => (
              <p key={kpi} className="rounded-md border p-2">{kpi}</p>
            )) : <p className="text-muted-foreground">No KPI set available yet.</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Funnel Strategy</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {funnelStrategy.length ? funnelStrategy.map((item) => (
              <p key={item} className="rounded-md border p-2">{item}</p>
            )) : <p className="text-muted-foreground">No funnel strategy available yet.</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Lead Magnets</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {leadMagnets.length ? leadMagnets.map((item) => (
              <p key={item} className="rounded-md border p-2">{item}</p>
            )) : <p className="text-muted-foreground">No lead magnet suggestions yet.</p>}
          </CardContent>
        </Card>
      </div>

      {workflowError ? (
        <Card className="border-destructive/40">
          <CardHeader>
            <CardTitle>Workflow Error</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-destructive">{workflowError}</p>
          </CardContent>
        </Card>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button className="gap-2" onClick={handleApprove} disabled={approvalMutation.isPending || !strategy || !strategyApprovalPending}>
          <ThumbsUp className="h-4 w-4" />
          {approvalMutation.isPending ? 'Submitting...' : 'Approve'}
        </Button>
        <Button variant="destructive" className="gap-2" onClick={handleReject} disabled={approvalMutation.isPending || !strategy || !strategyApprovalPending}>
          <ThumbsDown className="h-4 w-4" />
          Reject
        </Button>
        <Button
          variant="outline"
          className="gap-2"
          onClick={handleEditStrategy}
          disabled={approvalMutation.isPending || isRequestingEdits || !strategy || !strategyApprovalPending}
        >
          <Edit3 className="h-4 w-4" />
          Edit Strategy
        </Button>
      </div>
    </div>
  )
}
