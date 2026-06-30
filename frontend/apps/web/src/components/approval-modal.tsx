'use client'

import * as Dialog from '@radix-ui/react-dialog'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

type ApprovalModalProps = {
  open: boolean
  onOpenChange: (value: boolean) => void
  title: string
  onApprove: (approved: boolean, feedback: string) => Promise<void>
  isLoading?: boolean
}

export function ApprovalModal({ open, onOpenChange, title, onApprove, isLoading = false }: ApprovalModalProps) {
  const [feedback, setFeedback] = useState('')

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 w-[95vw] max-w-xl -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-card p-6 shadow-lg">
          <Dialog.Title className="text-lg font-semibold">{title}</Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-muted-foreground">
            Add optional feedback for the supervisor agent.
          </Dialog.Description>

          <Textarea
            className="mt-4"
            placeholder="Example: Increase LinkedIn share for enterprise audience"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            disabled={isLoading}
          />

          <div className="mt-6 flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isLoading}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={() => onApprove(false, feedback)} disabled={isLoading}>
              {isLoading ? 'Submitting...' : 'Reject'}
            </Button>
            <Button onClick={() => onApprove(true, feedback)} disabled={isLoading}>
              {isLoading ? 'Submitting...' : 'Approve'}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
