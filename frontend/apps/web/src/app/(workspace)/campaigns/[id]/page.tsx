'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import { useParams } from 'next/navigation'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AgentActivityTimeline } from '@/components/agent-activity-timeline'
import { ApprovalModal } from '@/components/approval-modal'
import { QAScenarioPanel } from '@/components/qa-scenario-panel'
import { StatusBadge } from '@/components/status-badge'
import { WebSocketErrorBoundary } from '@/components/websocket-error-boundary'
import { WebSocketReconnectState } from '@/components/websocket-reconnect-state'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { TabsNav } from '@/components/ui/tabs'
import { useToast } from '@/components/toaster'
import { useCampaign, useCampaignStatus } from '@/hooks/use-campaign-queries'
import { useCampaignWebSocket } from '@/hooks/useCampaignWebSocket'
import { approveCampaign } from '@/lib/api'
import { useCampaignStore } from '@/stores/campaign-store'

function normalizeApprovalType(value: unknown): 'strategy' | 'media_plan' {
  if (value === 'media_plan' || value === 'budget_approval') {
    return 'media_plan'
  }
  return 'strategy'
}

export default function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>()
  const campaignId = Array.isArray(id) ? id[0] : id
  const queryClient = useQueryClient()
  const { notify } = useToast()

  const [approvalOpen, setApprovalOpen] = useState(false)

  const { data: campaign } = useCampaign(campaignId)
  const { data: status } = useCampaignStatus(campaignId)
  const liveEvents = useCampaignStore((s) => s.realtimeEvents)
  const wsError = useCampaignStore((s) => s.websocketError)

  const ws = useCampaignWebSocket(campaignId)

  const approvalMutation = useMutation({
    mutationFn: async ({ approved, feedback }: { approved: boolean; feedback: string }) =>
      approveCampaign(campaignId, {
        approval_type: normalizeApprovalType(campaign?.pending_approval?.type),
        approved,
        feedback,
      }),
    onSuccess: () => {
      setApprovalOpen(false)
      notify('Approval submitted', 'Workflow has resumed')
      queryClient.invalidateQueries({ queryKey: ['campaign', campaignId] })
    },
  })

  const tabs = useMemo(
    () => [
      { label: 'Overview', href: `/campaigns/${campaignId}`, active: true },
      { label: 'Strategy', href: `/campaigns/${campaignId}/strategy` },
      { label: 'Content', href: `/campaigns/${campaignId}/content` },
      { label: 'Media', href: `/campaigns/${campaignId}` },
      { label: 'Performance', href: `/campaigns/${campaignId}/performance` },
      { label: 'Report', href: `/campaigns/${campaignId}/report` },
    ],
    [campaignId]
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">Campaign {campaignId}</h2>
          <p className="text-sm text-muted-foreground">Autonomous multi-agent execution state</p>
        </div>
        <StatusBadge status={status?.status ?? campaign?.status ?? 'running'} />
      </div>

      <TabsNav items={tabs} />

      <Card>
        <CardHeader>
          <CardTitle>Workflow Progress</CardTitle>
          <CardDescription>Current agent: {status?.current_agent ?? campaign?.current_agent ?? 'supervisor'}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Progress value={status?.progress_percentage ?? campaign?.progress_percentage ?? 0} />
          <p className="text-xs text-muted-foreground">WebSocket: {ws.status}</p>
          <p className="text-sm text-muted-foreground">
            Estimated completion:{' '}
            {status?.estimated_completion ? new Date(status.estimated_completion).toLocaleString() : 'calculating'}
          </p>
          {wsError ? <p className="text-sm text-destructive">{wsError}</p> : null}
        </CardContent>
      </Card>

      <WebSocketReconnectState />

      {campaign?.error ? (
        <Card className="border-destructive/40">
          <CardHeader>
            <CardTitle>Workflow Error</CardTitle>
            <CardDescription>The campaign stopped because of an agent/runtime failure.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-destructive">{campaign.error}</p>
          </CardContent>
        </Card>
      ) : null}

      {campaign?.pending_approval ? (
        <Card className="border-amber-500/40">
          <CardHeader>
            <CardTitle>Human Approval Required</CardTitle>
            <CardDescription>
              The workflow is waiting on {campaign.pending_approval.type} approval.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => setApprovalOpen(true)} disabled={approvalMutation.isPending}>
              {approvalMutation.isPending ? 'Submitting...' : 'Review Approval Request'}
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Output Snapshot</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>Strategy: {campaign?.strategy ? 'Available' : 'Pending'}</p>
            <p>Content assets: {campaign?.content?.assets ? String(campaign.content.assets.length) : 'Pending'}</p>
            <p>Media plan: {campaign?.media_plan ? 'Available' : 'Pending'}</p>
            <p>Performance report: {campaign?.performance ? 'Available' : 'Pending'}</p>
            <p>Final report: {campaign?.report ? 'Available' : 'Pending'}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button asChild variant="outline"><Link href={`/campaigns/${campaignId}/strategy`}>Open Strategy</Link></Button>
            <Button asChild variant="outline"><Link href={`/campaigns/${campaignId}/performance`}>Open Performance</Link></Button>
            <Button asChild><Link href={`/campaigns/${campaignId}/report`}>Open Report</Link></Button>
          </CardContent>
        </Card>
      </div>

      <QAScenarioPanel campaignId={campaignId} />

      <WebSocketErrorBoundary>
        <Card>
          <CardHeader>
            <CardTitle>Agent Activity Log</CardTitle>
            <CardDescription>Live timeline of supervisor and specialist agents.</CardDescription>
          </CardHeader>
          <CardContent>
            <AgentActivityTimeline
              items={
                liveEvents.length
                  ? liveEvents
                  : [
                      {
                        id: 'seed',
                        agent: status?.current_agent ?? 'supervisor',
                        status: status?.status ?? 'running',
                        message: 'Workflow initialized',
                        timestamp: new Date().toLocaleTimeString(),
                      },
                    ]
              }
            />
          </CardContent>
        </Card>
      </WebSocketErrorBoundary>

      <ApprovalModal
        open={approvalOpen}
        onOpenChange={setApprovalOpen}
        title="Approve plan"
        isLoading={approvalMutation.isPending}
        onApprove={async (approved, feedback) => {
          await approvalMutation.mutateAsync({ approved, feedback })
        }}
      />
    </div>
  )
}
