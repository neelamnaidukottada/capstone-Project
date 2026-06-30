import { motion } from 'framer-motion'

type ActivityItem = {
  id: string
  agent: string
  status: string
  message: string
  timestamp: string
}

export function AgentActivityTimeline({ items }: { items: ActivityItem[] }) {
  return (
    <div className="space-y-3">
      {items.map((item, index) => (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.03 }}
          key={item.id}
          className="rounded-lg border bg-card p-4"
        >
          <div className="flex items-center justify-between">
            <p className="font-medium">{item.agent}</p>
            <p className="text-xs text-muted-foreground">{item.timestamp}</p>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{item.message}</p>
          <p className="mt-2 text-xs uppercase tracking-wide text-primary">{item.status}</p>
        </motion.div>
      ))}
    </div>
  )
}
