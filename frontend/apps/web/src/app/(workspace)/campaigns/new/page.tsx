'use client'

import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { createCampaign } from '@/lib/api'
import { useToast } from '@/components/toaster'

const steps = ['Goal', 'Budget', 'Timeline', 'Review'] as const

export default function NewCampaignPage() {
  const [step, setStep] = useState(0)
  const [campaignName, setCampaignName] = useState('')
  const [goal, setGoal] = useState('')
  const [contentRequest, setContentRequest] = useState('')
  const [targetAudience, setTargetAudience] = useState('')
  const [industry, setIndustry] = useState('')
  const [productDescription, setProductDescription] = useState('')
  const [budget, setBudget] = useState(0)
  const [timelineDays, setTimelineDays] = useState(0)
  const [chatPrompt, setChatPrompt] = useState('')
  const [chatSuggestions, setChatSuggestions] = useState<string[]>([])

  const router = useRouter()
  const { notify } = useToast()

  const estimate = useMemo(() => {
    const daily = Math.round(budget / Math.max(timelineDays, 1))
    const projectedLeads = Math.round((budget / 120) * 1.45)
    return { daily, projectedLeads }
  }, [budget, timelineDays])

  const submitMutation = useMutation({
    mutationFn: () => {
      const sanitizedBudget = Number.isFinite(budget) ? budget : 0
      const sanitizedDays = Number.isFinite(timelineDays) && timelineDays >= 1 ? Math.round(timelineDays) : 0

      const errors: string[] = []
      if (!campaignName.trim() || campaignName.trim().length < 2) errors.push('Campaign name must be at least 2 characters')
      if (!goal.trim() || goal.trim().length < 5) errors.push('Goal must be at least 5 characters')
      if (!contentRequest.trim() || contentRequest.trim().length < 5) {
        errors.push('Content request must be at least 5 characters')
      }
      if (!industry.trim() || industry.trim().length < 2) errors.push('Industry must be at least 2 characters')
      if (!productDescription.trim() || productDescription.trim().length < 10) errors.push('Product description must be at least 10 characters')
      if (sanitizedBudget < 0) errors.push('Budget cannot be negative')
      if (sanitizedDays < 1) errors.push('Timeline must be at least 1 day')
      if (errors.length > 0) return Promise.reject(new Error(errors.join(' | ')))

      return createCampaign({
        campaign_name: campaignName.trim(),
        content_request: contentRequest.trim(),
        goal: {
          goal: goal.trim(),
          budget: sanitizedBudget,
          timeline_days: sanitizedDays,
          target_audience: targetAudience.trim() || null,
          industry: industry.trim(),
          product_description: productDescription.trim(),
        },
        human_in_the_loop: true,
        auto_approve: false,
      })
    },
    onSuccess: (res) => {
      notify('Campaign created', `Workflow started for ${res.campaign_id}`)
      router.push(`/campaigns/${res.campaign_id}`)
    },
    onError: (err) => notify('Unable to create campaign', err instanceof Error ? err.message : 'Please try again'),
  })

  const refineGoal = () => {
    if (!chatPrompt.trim()) return
    const suggestion = `Refined goal: ${goal}. Add focus on ${chatPrompt.trim()} with explicit KPI milestones.`
    setChatSuggestions((prev) => [suggestion, ...prev].slice(0, 4))
    setGoal(`${goal} while optimizing for ${chatPrompt.trim()}`)
    setChatPrompt('')
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-muted-foreground">Campaign Builder</p>
        <h2 className="text-3xl font-bold">New Autonomous Campaign</h2>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {steps.map((item, index) => (
          <Card key={item} className={index === step ? 'border-primary' : ''}>
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground">Step {index + 1}</p>
              <p className="font-medium">{item}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <motion.div key={step} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        {step === 0 ? (
          <Card>
            <CardHeader>
              <CardTitle>Define Goal</CardTitle>
              <CardDescription>Set the campaign objective and refine with AI chat assist.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input value={campaignName} onChange={(e) => setCampaignName(e.target.value)} placeholder="Campaign name" />
              <Textarea value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="Primary business objective" />
              <Textarea
                value={contentRequest}
                onChange={(e) => setContentRequest(e.target.value)}
                placeholder="Content request (e.g., Create content for LinkedIn, Facebook, Email, and Google Ads.)"
              />
              <Input value={targetAudience} onChange={(e) => setTargetAudience(e.target.value)} placeholder="Target audience (optional)" />
              <Input value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="Industry" />
              <Textarea value={productDescription} onChange={(e) => setProductDescription(e.target.value)} placeholder="Product description" />

              <div className="rounded-lg border bg-muted/40 p-4">
                <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                  <Sparkles className="h-4 w-4" />
                  AI-assisted goal refinement
                </div>
                <div className="flex gap-2">
                  <Input value={chatPrompt} onChange={(e) => setChatPrompt(e.target.value)} placeholder="Try: improve qualified pipeline from enterprise accounts" />
                  <Button onClick={refineGoal}>Refine</Button>
                </div>
                <div className="mt-3 space-y-2">
                  {chatSuggestions.map((s) => (
                    <p key={s} className="rounded-md bg-background p-2 text-sm text-muted-foreground">
                      {s}
                    </p>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        ) : null}

        {step === 1 ? (
          <Card>
            <CardHeader>
              <CardTitle>Budget</CardTitle>
              <CardDescription>Set budget and review real-time cost estimation.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input type="number" value={budget} onChange={(e) => { const v = parseFloat(e.target.value); if (!isNaN(v)) setBudget(v) }} min={0} />
              <div className="rounded-lg border bg-muted/40 p-4">
                <p className="text-sm">Estimated daily spend: ${estimate.daily.toLocaleString()}</p>
                <p className="text-sm">Projected qualified leads: {estimate.projectedLeads.toLocaleString()}</p>
              </div>
            </CardContent>
          </Card>
        ) : null}

        {step === 2 ? (
          <Card>
            <CardHeader>
              <CardTitle>Timeline</CardTitle>
              <CardDescription>Define campaign duration.</CardDescription>
            </CardHeader>
            <CardContent>
              <Input type="number" value={timelineDays} onChange={(e) => { const v = parseInt(e.target.value, 10); if (!isNaN(v)) setTimelineDays(v) }} min={1} />
            </CardContent>
          </Card>
        ) : null}

        {step === 3 ? (
          <Card>
            <CardHeader>
              <CardTitle>Review & Submit</CardTitle>
              <CardDescription>Confirm details and trigger the agent workflow.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p><strong>Campaign Name:</strong> {campaignName || <span className="text-destructive">Required (min 2 chars)</span>}</p>
              <p><strong>Goal:</strong> {goal || <span className="text-destructive">Required (min 5 chars)</span>}</p>
              <p><strong>Content Request:</strong> {contentRequest || <span className="text-destructive">Required (min 5 chars)</span>}</p>
              <p><strong>Budget:</strong> {budget >= 0 ? `$${budget.toLocaleString()}` : <span className="text-destructive">Required (must be &gt;= 0)</span>}</p>
              <p><strong>Timeline:</strong> {timelineDays >= 1 ? `${timelineDays} days` : <span className="text-destructive">Required (min 1 day)</span>}</p>
              <p><strong>Target:</strong> {targetAudience || <span className="text-muted-foreground">Optional - AI will make reasonable assumptions</span>}</p>
              <p><strong>Industry:</strong> {industry || <span className="text-destructive">Required (min 2 chars)</span>}</p>
              <p><strong>Product:</strong> {productDescription || <span className="text-destructive">Required (min 10 chars)</span>}</p>
            </CardContent>
          </Card>
        ) : null}
      </motion.div>

      <div className="flex justify-between">
        <Button variant="outline" disabled={step === 0} onClick={() => setStep((s) => Math.max(0, s - 1))}>
          Back
        </Button>
        {step < steps.length - 1 ? (
          <Button onClick={() => setStep((s) => Math.min(steps.length - 1, s + 1))}>Continue</Button>
        ) : (
          <Button onClick={() => submitMutation.mutate()} disabled={submitMutation.isPending}>
            {submitMutation.isPending ? 'Submitting...' : 'Submit Campaign'}
          </Button>
        )}
      </div>
    </div>
  )
}
