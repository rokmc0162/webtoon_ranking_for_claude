import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";

export default function Loading() {
  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-[900px] mx-auto px-3 sm:px-6 py-4">
        <div className="flex items-center gap-3 mb-4">
          <Skeleton className="w-12 h-5 rounded" />
          <Separator orientation="vertical" className="h-4" />
          <Skeleton className="w-20 h-4 rounded" />
        </div>

        <div className="space-y-4">
          <Skeleton className="h-[180px] w-full rounded-xl" />
          <Skeleton className="h-[300px] w-full rounded-xl" />
          <Skeleton className="h-[120px] w-full rounded-xl" />
          <Skeleton className="h-[200px] w-full rounded-xl" />
        </div>
      </div>
    </div>
  );
}
