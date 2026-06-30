import { Skeleton } from '@/components/ui/skeleton'

export default function CampaignLoading() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-40 w-full" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Skeleton className="h-36" />
        <Skeleton className="h-36" />
      </div>
      <Skeleton className="h-72" />
    </div>
  )
}
