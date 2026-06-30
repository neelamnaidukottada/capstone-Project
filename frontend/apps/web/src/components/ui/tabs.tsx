import Link from 'next/link'
import type { Route } from 'next'
import { cn } from '@/lib/utils'

export type TabItem = { label: string; href: string; active?: boolean }

export function TabsNav({ items, className }: { items: TabItem[]; className?: string }) {
  return (
    <div className={cn('flex flex-wrap gap-2 rounded-lg border bg-card p-2', className)}>
      {items.map((item, index) => (
        <Link
          key={`${item.href}-${item.label}-${index}`}
          href={item.href as Route}
          className={cn(
            'rounded-md px-3 py-2 text-sm font-medium transition-colors',
            item.active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'
          )}
        >
          {item.label}
        </Link>
      ))}
    </div>
  )
}
