"use client";

import type { PlatformComparison } from "@/lib/trend-report";

const RV = "#0D3B70";

export function PlatformComparisonSection({ platforms }: { platforms: PlatformComparison[] }) {
  if (!platforms || platforms.length === 0) return null;

  const maxTotal = Math.max(...platforms.map((p) => p.total_ranked), 1);

  // 리버스 있는 플랫폼 먼저, 그 다음 총수 순
  const sorted = [...platforms].sort((a, b) => {
    if (a.riverse_count > 0 && b.riverse_count === 0) return -1;
    if (a.riverse_count === 0 && b.riverse_count > 0) return 1;
    return b.total_ranked - a.total_ranked;
  });

  return (
    <div className="rounded-xl bg-card border border-border/50 shadow-sm overflow-hidden">
      <div className="px-4 py-3" style={{ borderBottom: `1px solid ${RV}15` }}>
        <h3 className="text-xs font-bold text-foreground flex items-center gap-1.5">
          <span>🏢</span>
          플랫폼별 리버스 현황
        </h3>
      </div>

      <div className="px-4 py-3 space-y-2">
        {sorted.map((p) => {
          const rvPct = p.total_ranked > 0 ? (p.riverse_count / p.total_ranked) * 100 : 0;
          const barWidth = (p.total_ranked / maxTotal) * 100;

          return (
            <div key={p.platform} className="flex items-center gap-2">
              {/* 플랫폼명 */}
              <span className="text-[11px] font-medium w-16 sm:w-20 shrink-0 truncate">
                {p.platform_name}
              </span>

              {/* 스택 바 */}
              <div className="flex-1 h-5 bg-muted/30 rounded overflow-hidden relative">
                <div
                  className="h-full flex"
                  style={{ width: `${Math.max(barWidth, 8)}%` }}
                >
                  {/* 리버스 부분 */}
                  {p.riverse_count > 0 && (
                    <div
                      className="h-full transition-all duration-500"
                      style={{
                        width: `${rvPct}%`,
                        backgroundColor: RV,
                        minWidth: "4px",
                      }}
                    />
                  )}
                  {/* 비리버스 부분 */}
                  <div
                    className="h-full transition-all duration-500"
                    style={{
                      width: `${100 - rvPct}%`,
                      backgroundColor: p.platform_color + "60",
                    }}
                  />
                </div>
              </div>

              {/* 숫자 */}
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="text-[10px] font-mono text-muted-foreground w-12 text-right">
                  {p.riverse_count > 0 ? (
                    <>
                      <span className="font-bold" style={{ color: RV }}>{p.riverse_count}</span>
                      <span>/{p.total_ranked}</span>
                    </>
                  ) : (
                    <span>0/{p.total_ranked}</span>
                  )}
                </span>
                {p.riverse_count > 0 && (
                  <span
                    className="text-[9px] px-1 py-0.5 rounded font-bold shrink-0"
                    style={{ backgroundColor: RV + "15", color: RV }}
                  >
                    {p.share_pct}%
                  </span>
                )}
                {p.avg_riverse_rank && (
                  <span className="text-[9px] text-muted-foreground font-mono">
                    avg {p.avg_riverse_rank}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 범례 */}
      <div className="px-4 pb-3 flex items-center gap-4 text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: RV }} />
          리버스
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-gray-300" />
          타사
        </span>
      </div>
    </div>
  );
}
