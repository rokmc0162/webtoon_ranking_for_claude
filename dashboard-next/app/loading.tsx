import { Skeleton } from "@/components/ui/skeleton";

// 서버 컴포넌트 데이터 로드 중 표시되는 즉시 로딩 UI (스트리밍 SSR)
export default function Loading() {
  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-[1200px] mx-auto px-3 sm:px-6">
        {/* Header skeleton */}
        <header className="flex items-center justify-center gap-3 py-4 border-b border-border">
          <Skeleton className="w-9 h-9 rounded" />
          <Skeleton className="w-48 h-7 rounded" />
        </header>

        {/* Date selector skeleton */}
        <div className="flex items-center justify-between mt-4 mb-3">
          <Skeleton className="w-[200px] h-10 rounded-md" />
          <Skeleton className="w-32 h-4 rounded" />
        </div>

        {/* Platform tabs skeleton */}
        <div className="grid grid-cols-4 sm:grid-cols-6 gap-2 sm:gap-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <Skeleton key={i} className="h-[88px] rounded-xl" />
          ))}
        </div>

        {/* Genre pills skeleton */}
        <div className="flex flex-wrap gap-1.5 mt-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="w-16 h-7 rounded-full" />
          ))}
        </div>

        {/* Filter bar skeleton */}
        <div className="flex items-center justify-between mt-4 mb-2">
          <Skeleton className="w-64 h-5 rounded" />
          <Skeleton className="w-24 h-5 rounded" />
        </div>

        {/* Ranking table skeleton */}
        <div className="space-y-2 mt-2">
          {Array.from({ length: 15 }).map((_, i) => (
            <Skeleton key={i} className="h-[72px] w-full rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  );
}
