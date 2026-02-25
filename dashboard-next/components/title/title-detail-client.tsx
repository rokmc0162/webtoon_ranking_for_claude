"use client";

import { useRouter } from "next/navigation";
import { TitleHero } from "@/components/title/title-hero";
import dynamic from "next/dynamic";
const RankHistoryChart = dynamic(
  () => import("@/components/title/rank-history-chart").then((m) => m.RankHistoryChart),
  { ssr: false, loading: () => <div className="h-64 bg-muted animate-pulse rounded-lg" /> }
);
import { PlatformMetrics } from "@/components/title/platform-metrics";
import { CrossPlatformTable } from "@/components/title/cross-platform-table";
import { ReviewSectionWithLoadMore } from "@/components/title/review-section-loadmore";
import { AiAnalysis } from "@/components/title/ai-analysis";
import { ExternalData } from "@/components/title/external-data";
import { Separator } from "@/components/ui/separator";
import { getPlatformById } from "@/lib/constants";
import type { TitleDetailResponse } from "@/lib/types";

interface TitleDetailClientProps {
  data: TitleDetailResponse;
}

export function TitleDetailClient({ data }: TitleDetailClientProps) {
  const router = useRouter();
  const platform = data.metadata.platform;
  const title = data.metadata.title;

  const platformInfo = getPlatformById(platform);
  const platformColor = platformInfo?.color || "#0D3B70";
  const platformName = platformInfo?.name || platform;

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
            작품 상세 분석
          </span>
        </div>

        <div className="space-y-4">
          {/* 1. 히어로 섹션 */}
          <TitleHero
            metadata={data.metadata}
            platformColor={platformColor}
            platformName={platformName}
          />

          {/* 2. 랭킹 추이 차트 */}
          <RankHistoryChart
            data={data.rankHistory}
            platform={platform}
            platformColor={platformColor}
            crossPlatform={data.crossPlatform}
          />

          {/* 3. 플랫폼 지표 */}
          <PlatformMetrics
            metadata={data.metadata}
            reviewStats={data.reviewStats}
            platformColor={platformColor}
          />

          {/* 4. AI 작품 분석 */}
          <AiAnalysis
            platform={platform}
            title={title}
            platformColor={platformColor}
          />

          {/* 5. 크로스 플랫폼 비교 */}
          <CrossPlatformTable
            entries={data.crossPlatform}
            currentPlatform={platform}
          />

          {/* 6. 리뷰 섹션 (더보기 지원) */}
          <ReviewSectionWithLoadMore
            initialReviews={data.reviews}
            totalReviews={data.reviewStats.total}
            platform={platform}
            title={title}
            platformColor={platformColor}
          />

          {/* 7. 외부 평가 데이터 */}
          <ExternalData
            title={title}
            platformColor={platformColor}
          />
        </div>

        {/* 푸터 */}
        <Separator className="mt-8" />
        <footer className="py-4 text-center text-xs text-muted-foreground">
          RIVERSE Inc. | 작품 상세 분석
        </footer>
      </div>
    </div>
  );
}
