import React from 'react'
import { Badge, type BadgeProps } from '@/components/ui/badge'

type BadgeVariant = NonNullable<BadgeProps['variant']>

export function StatusBadge({ status }: { status: string }) {
  const variant: BadgeVariant =
    status === 'completed'
      ? 'success'
      : status.includes('approval')
        ? 'warning'
        : status === 'failed'
          ? 'destructive'
          : 'secondary'

  return <Badge variant={variant}>{status.replaceAll('_', ' ')}</Badge>
}
