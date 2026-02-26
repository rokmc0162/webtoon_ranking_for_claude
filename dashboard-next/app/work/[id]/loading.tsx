import { Skeleton } from "@/components/ui/skeleton";

export default function WorkLoading() {
  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-[1000px] mx-auto px-3 sm:px-6 py-6">
        {/* Hero skeleton */}
        <div className="flex gap-4 mb-6">
          <Skeleton className="w-[120px] h-[160px] rounded-lg flex-shrink-0" />
          <div className="flex-1 space-y-3">
            <Skeleton className="w-48 h-7 rounded" />
            <Skeleton className="w-32 h-5 rounded" />
            <Skeleton className="w-64 h-4 rounded" />
            <Skeleton className="w-full h-4 rounded" />
          </div>
        </div>

        {/* Chart skeleton */}
        <Skeleton className="w-full h-[300px] rounded-xl mb-6" />

        {/* Platform table skeleton */}
        <div className="space-y-2 mb-6">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-[60px] w-full rounded-lg" />
          ))}
        </div>

        {/* Reviews skeleton */}
        <Skeleton className="w-32 h-6 rounded mb-3" />
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-[80px] w-full rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  );
}
