import { Skeleton } from '@/components/ui/skeleton'

export default function ReportLoading() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-40" />
      <Skeleton className="h-40" />
      <Skeleton className="h-72" />
      <Skeleton className="h-28" />
    </div>
  )
}
