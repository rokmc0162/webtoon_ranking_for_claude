"use client";

import { useState } from "react";
import Link from "next/link";
import { getPlatformById } from "@/lib/constants";
import type { TrendReport } from "@/lib/trend-report";

function PlatformBadge({ platform }: { platform: string }) {
  const info = getPlatformById(platform);
  const color = info?.color ?? "#666";
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium text-white shrink-0"
      style={{ backgroundColor: color }}
    >
      {info?.name ?? platform}
    </span>
  );
}

function RankChange({ change }: { change: number }) {
  if (change > 0) {
    return <span className="text-emerald-500 font-semibold text-xs">+{change}</span>;
  }
  if (change < 0) {
    return <span className="text-red-500 font-semibold text-xs">{change}</span>;
  }
  return <span className="text-muted-foreground text-xs">-</span>;
}

function WorkLink({
  unifiedWorkId,
  children,
}: {
  unifiedWorkId: number | null;
  children: React.ReactNode;
}) {
  if (unifiedWorkId) {
    return (
      <Link
        href={`/work/${unifiedWorkId}`}
        className="hover:underline hover:text-primary transition-colors"
      >
        {children}
      </Link>
    );
  }
  return <>{children}</>;
}

function ShareBar({ pct }: { pct: number }) {
  return (
    <div className="flex items-center gap-2 flex-1">
      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-primary/70 rounded-full transition-all"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground w-9 text-right">{pct}%</span>
    </div>
  );
}

function formatDate(dateStr: string): string {
  const parts = dateStr.split("-");
  if (parts.length === 3) {
    return `${parseInt(parts[1])}/${parseInt(parts[2])}`;
  }
  return dateStr;
}

export function TrendReportCard({ report }: { report?: TrendReport | null }) {
  const [detailOpen, setDetailOpen] = useState(false);

  if (!report) return null;

  const { riverse_summary, rising_works, new_entries, multi_platform, platform_riverse_share } =
    report;

  return (
    <div className="bg-card border rounded-xl overflow-hidden mb-4">
      {/* 타이틀 */}
      <div className="px-4 pt-4 pb-2">
        <h2 className="text-sm font-bold text-foreground flex items-center gap-1.5">
          <span>📊</span>
          JP 웹툰 트렌드 리포트
          <span className="text-xs font-normal text-muted-foreground ml-1">
            {report.data_date}
          </span>
        </h2>
      </div>

      {/* 해석적 요약문 (항상 표시) */}
      <div className="px-4 pb-3">
        <div className="text-sm text-foreground/85 leading-relaxed whitespace-pre-line">
          {report.summary}
        </div>
      </div>

      {/* 상세 토글 */}
      <div className="px-4 pb-3">
        <button
          onClick={() => setDetailOpen(!detailOpen)}
          className="text-xs text-blue-500 hover:text-blue-600 hover:bg-muted/50 px-2.5 py-1.5 rounded-lg transition-colors cursor-pointer"
        >
          {detailOpen ? "📋 상세 데이터 접기" : "📋 상세 데이터 보기"}
        </button>
      </div>

      {/* 상세 데이터 패널 */}
      {detailOpen && (
        <div className="px-4 pb-4 space-y-5 border-t">
          {/* Section 1: Riverse TOP */}
          {riverse_summary.top_riverse.length > 0 && (
            <section className="pt-4">
              <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
                🏆 리버스 TOP 랭킹
              </h3>
              <div className="space-y-1">
                {riverse_summary.top_riverse.map((w, i) => (
                  <div
                    key={`${w.platform}-${w.rank}-${i}`}
                    className="flex items-center gap-2 text-sm"
                  >
                    <span className="text-muted-foreground w-9 text-right shrink-0 whitespace-nowrap">
                      {w.rank}위
                    </span>
                    <WorkLink unifiedWorkId={w.unified_work_id}>
                      <span className="font-medium truncate">{w.title_kr}</span>
                    </WorkLink>
                    <PlatformBadge platform={w.platform} />
                    <RankChange change={w.rank_change} />
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Section 2: Rising Works */}
          {rising_works.length > 0 && (
            <section>
              <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
                🚀 급상승 작품
              </h3>
              <div className="space-y-1">
                {rising_works.map((w, i) => (
                  <div
                    key={`${w.platform}-${w.title}-${i}`}
                    className="flex items-center gap-2 text-sm"
                  >
                    <WorkLink unifiedWorkId={w.unified_work_id}>
                      <span className="font-medium truncate">
                        {w.title_kr || w.title}
                      </span>
                    </WorkLink>
                    <span className="text-muted-foreground text-xs shrink-0">
                      {w.prev_rank}→{w.curr_rank}위
                    </span>
                    <span className="text-emerald-500 font-semibold text-xs shrink-0">
                      (+{w.change})
                    </span>
                    <PlatformBadge platform={w.platform} />
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Section 3: New Entries */}
          {new_entries.length > 0 && (
            <section>
              <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
                🆕 신규 진입
              </h3>
              <div className="space-y-1">
                {new_entries.map((w, i) => (
                  <div
                    key={`${w.platform}-${w.title}-${i}`}
                    className="flex items-center gap-2 text-sm"
                  >
                    <WorkLink unifiedWorkId={w.unified_work_id}>
                      <span className="font-medium truncate">
                        {w.title_kr || w.title}
                      </span>
                    </WorkLink>
                    <PlatformBadge platform={w.platform} />
                    <span className="text-muted-foreground text-xs shrink-0">
                      #{w.rank}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Section 4: Multi-platform */}
          {multi_platform.length > 0 && (
            <section>
              <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
                🌐 멀티플랫폼 인기작
              </h3>
              <div className="space-y-2">
                {multi_platform.map((w, i) => (
                  <div key={`multi-${i}`} className="text-sm">
                    <div className="flex items-center gap-2 mb-0.5">
                      <WorkLink unifiedWorkId={w.unified_work_id}>
                        <span className="font-medium">{w.title_kr}</span>
                      </WorkLink>
                      <span className="text-muted-foreground text-xs">
                        ({w.platform_count}개 플랫폼)
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1 ml-2">
                      {w.platforms.map((p) => (
                        <span
                          key={p.platform}
                          className="inline-flex items-center gap-0.5 text-xs text-muted-foreground"
                        >
                          <PlatformBadge platform={p.platform} />
                          <span>#{p.rank}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Section 5: Platform Riverse Share */}
          {platform_riverse_share.length > 0 && (
            <section>
              <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
                📈 플랫폼별 리버스 점유율
              </h3>
              <div className="space-y-1.5">
                {platform_riverse_share.filter((p) => p.riverse_count > 0).map((p) => (
                  <div
                    key={p.platform}
                    className="flex items-center gap-2 text-sm"
                  >
                    <span className="w-20 shrink-0 truncate text-xs font-medium">
                      {p.platform_name}
                    </span>
                    <span className="text-muted-foreground text-xs w-14 shrink-0">
                      {p.riverse_count}/{p.total_ranked}
                    </span>
                    <ShareBar pct={p.share_pct} />
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
