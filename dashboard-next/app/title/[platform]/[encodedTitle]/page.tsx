"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { TitleHero } from "@/components/title/title-hero";
import { RankHistoryChart } from "@/components/title/rank-history-chart";
import { PlatformMetrics } from "@/components/title/platform-metrics";
import { CrossPlatformTable } from "@/components/title/cross-platform-table";
import { ReviewSection } from "@/components/title/review-section";
import { AiAnalysis } from "@/components/title/ai-analysis";
import { ExternalData } from "@/components/title/external-data";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { getPlatformById } from "@/lib/constants";
import type { TitleDetailResponse } from "@/lib/types";

export default function TitleDetailPage() {
  const params = useParams();
  const router = useRouter();
  const platform = params.platform as string;
  const encodedTitle = params.encodedTitle as string;
  const title = decodeURIComponent(encodedTitle);

  const [data, setData] = useState<TitleDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const platformInfo = getPlatformById(platform);
  const platformColor = platformInfo?.color || "#0D3B70";
  const platformName = platformInfo?.name || platform;

  useEffect(() => {
    if (!platform || !title) return;
    setLoading(true);
    setError("");

    fetch(
      `/api/title-detail?platform=${encodeURIComponent(platform)}&title=${encodeURIComponent(title)}`
    )
      .then((res) => {
        if (!res.ok) throw new Error("not found");
        return res.json();
      })
      .then((d: TitleDetailResponse) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => {
        setError("작품 정보를 불러올 수 없습니다.");
        setLoading(false);
      });
  }, [platform, title]);

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

        {loading ? (
          <div className="space-y-4">
            <Skeleton className="h-[180px] w-full rounded-xl" />
            <Skeleton className="h-[400px] w-full rounded-xl" />
            <Skeleton className="h-[200px] w-full rounded-xl" />
          </div>
        ) : error ? (
          <div className="text-center py-20 text-muted-foreground">
            <p className="text-lg mb-2">{error}</p>
            <button
              onClick={() => router.back()}
              className="text-sm text-blue-500 hover:underline cursor-pointer"
            >
              랭킹으로 돌아가기
            </button>
          </div>
        ) : data ? (
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

            {/* 6. 리뷰 섹션 */}
            <ReviewSection
              reviews={data.reviews}
              platform={platform}
              platformColor={platformColor}
            />

            {/* 7. 외부 평가 데이터 */}
            <ExternalData
              title={title}
              platformColor={platformColor}
            />
          </div>
        ) : null}

        {/* 푸터 */}
        <Separator className="mt-8" />
        <footer className="py-4 text-center text-xs text-muted-foreground">
          RIVERSE Inc. | 작품 상세 분석
        </footer>
      </div>
    </div>
  );
}
