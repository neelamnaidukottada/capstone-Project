'use client'

import { useMemo, useState } from 'react'
import { useParams } from 'next/navigation'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Download, Share2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/components/toaster'
import { useCampaign, useCampaignReport } from '@/hooks/use-campaign-queries'

type CampaignReportSummary = {
  executive_summary?: string
}

type ReportSection = {
  title?: string
  bullets?: string[]
}

type MediaPlanChannel = {
  channel?: string
  budget?: number
}

export default function CampaignReportPage() {
  const { id } = useParams<{ id: string }>()
  const campaignId = Array.isArray(id) ? id[0] : id
  const [format, setFormat] = useState<'json' | 'markdown' | 'pdf'>('json')

  const { data: campaign } = useCampaign(campaignId)
  const { data: report } = useCampaignReport(campaignId, format)
  const { notify } = useToast()
  const reportSummary = (report?.content as CampaignReportSummary | undefined)?.executive_summary
  const campaignSummary = (campaign?.report as CampaignReportSummary | null | undefined)?.executive_summary

  const bestWorst = useMemo(() => {
    const finalReport = campaign?.report as { detailed_sections?: ReportSection[] } | null | undefined
    const detailed = finalReport?.detailed_sections ?? []
    const perfSection = detailed.find((section) => section.title === 'Detailed Performance')
    const bullets = perfSection?.bullets ?? []

    const best = bullets.find((item) => item.toLowerCase().startsWith('best performing channel:'))
    const worst = bullets.find((item) => item.toLowerCase().startsWith('worst performing channel:'))

    return {
      best: best ? best.split(':').slice(1).join(':').trim() : null,
      worst: worst ? worst.split(':').slice(1).join(':').trim() : null,
    }
  }, [campaign?.report])

  const downloadReport = (selected: 'json' | 'markdown' | 'pdf') => {
    if (!report) {
      notify('Report not ready', 'Try again after generation completes')
      return
    }

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
    const filenameBase = `campaign-${campaignId}-report-${timestamp}`

    if (selected === 'pdf') {
      if (typeof report.content === 'string') {
        const link = document.createElement('a')
        link.href = `data:application/pdf;base64,${report.content}`
        link.download = `${filenameBase}.pdf`
        link.click()
        notify('PDF downloaded')
        return
      }
      notify('PDF unavailable', 'Server did not return PDF bytes')
      return
    }

    const content =
      selected === 'markdown'
        ? String(report.content ?? '')
        : JSON.stringify(report.content ?? {}, null, 2)

    const mime = selected === 'markdown' ? 'text/markdown;charset=utf-8' : 'application/json;charset=utf-8'
    const extension = selected === 'markdown' ? 'md' : 'json'
    const blob = new Blob([content], { type: mime })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${filenameBase}.${extension}`
    link.click()
    URL.revokeObjectURL(url)
    notify(`${selected.toUpperCase()} downloaded`)
  }

  const chartData = useMemo(() => {
    const channels =
      ((campaign?.media_plan as { channels?: MediaPlanChannel[] } | null | undefined)?.channels ?? [])
        .filter((item) => item.channel)
        .map((item) => ({
          name: String(item.channel),
          spend: Number(item.budget ?? 0),
        }))

    return channels
  }, [campaign?.media_plan])

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">Final Report</h2>
          <p className="text-sm text-muted-foreground">Executive summary and export options</p>
        </div>

        <div className="flex gap-2">
          <Button variant={format === 'json' ? 'default' : 'outline'} onClick={() => setFormat('json')}>JSON</Button>
          <Button variant={format === 'markdown' ? 'default' : 'outline'} onClick={() => setFormat('markdown')}>Markdown</Button>
          <Button variant={format === 'pdf' ? 'default' : 'outline'} onClick={() => setFormat('pdf')}>PDF</Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Executive Summary</CardTitle>
          <CardDescription>{campaign?.status ?? 'Report in progress'}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-7 text-muted-foreground">
            {String(
              reportSummary ??
                campaignSummary ??
                'Executive summary will appear when the reporter completes the final report.'
            )}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Interactive Charts</CardTitle>
        </CardHeader>
        <CardContent className="h-[320px]">
          {chartData.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="spend" fill="#0284c7" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted-foreground">Channel spend chart will populate after media planning completes.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Channel Performance Summary</CardTitle>
          <CardDescription>Best and worst performing channels from the final report.</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2 text-sm">
          <div className="rounded-md border p-3">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Best Channel</p>
            <p className="mt-1 font-medium">{bestWorst.best ?? 'Not available yet'}</p>
          </div>
          <div className="rounded-md border p-3">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Worst Channel</p>
            <p className="mt-1 font-medium">{bestWorst.worst ?? 'Not available yet'}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Export & Share</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button className="gap-2" onClick={() => downloadReport('pdf')}><Download className="h-4 w-4" />Download PDF</Button>
          <Button variant="outline" className="gap-2" onClick={() => downloadReport('markdown')}><Download className="h-4 w-4" />Download Markdown</Button>
          <Button variant="outline" className="gap-2" onClick={() => downloadReport('json')}><Download className="h-4 w-4" />Download JSON</Button>
          <Button
            variant="outline"
            className="gap-2"
            onClick={() => {
              navigator.clipboard.writeText(window.location.href)
              notify('Report link copied')
            }}
          >
            <Share2 className="h-4 w-4" />Share Report
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Report Payload ({report?.format ?? format})</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="max-h-72 overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(report?.content ?? {}, null, 2)}</pre>
        </CardContent>
      </Card>
    </div>
  )
}
