"use client";

import { useRouter } from "next/navigation";
import { UnifiedHero } from "@/components/work/unified-hero";
import dynamic from "next/dynamic";
const UnifiedRankChart = dynamic(
  () => import("@/components/work/unified-rank-chart").then((m) => m.UnifiedRankChart),
  { ssr: false, loading: () => <div className="h-64 bg-muted animate-pulse rounded-lg" /> }
);
import { UnifiedPlatformTable } from "@/components/work/unified-platform-table";
import { UnifiedAiAnalysis } from "@/components/work/unified-ai-analysis";
import { UnifiedReviews } from "@/components/work/unified-reviews";
import { Separator } from "@/components/ui/separator";
import type { UnifiedWorkResponse } from "@/lib/types";

interface UnifiedWorkClientProps {
  data: UnifiedWorkResponse;
}

export function UnifiedWorkClient({ data }: UnifiedWorkClientProps) {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-[900px] mx-auto px-3 sm:px-6 py-4">
        {/* 헤더 */}
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={() => router.back()}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer flex items-center gap-1"
          >
            ← 뒤로
          </button>
          <Separator orientation="vertical" className="h-4" />
          <span className="text-xs text-muted-foreground">
            통합 작품 분석
          </span>
        </div>

        <div className="space-y-4">
          {/* 1. 히어로 섹션 (통합 메타 + 플랫폼 배지들) */}
          <UnifiedHero
            metadata={data.metadata}
            platforms={data.platforms}
          />

          {/* 2. 멀티 플랫폼 랭킹 추이 차트 */}
          <UnifiedRankChart platforms={data.platforms} />

          {/* 3. 플랫폼별 상세 비교 테이블 */}
          <UnifiedPlatformTable platforms={data.platforms} />

          {/* 4. AI 작품 분석 */}
          <UnifiedAiAnalysis workId={data.metadata.id} />

          {/* 5. 통합 리뷰 (더보기 지원) */}
          <UnifiedReviews
            initialReviews={data.reviews}
            totalReviews={data.reviewStats.total}
            reviewStats={data.reviewStats}
            workId={data.metadata.id}
          />
        </div>

        {/* 푸터 */}
        <Separator className="mt-8" />
        <footer className="py-4 text-center text-xs text-muted-foreground">
          RIVERSE Inc. | 통합 작품 분석
        </footer>
      </div>
    </div>
  );
}
