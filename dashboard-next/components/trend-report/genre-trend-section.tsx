"use client";

import { useState } from "react";
import type { GenreTrend } from "@/lib/trend-report";

const RV = "#0D3B70";
const RV_LIGHT = "#E8EEF5";

function DeltaBadge({ delta }: { delta: number }) {
  if (delta === 0) return <span className="text-[10px] text-muted-foreground">—</span>;
  const isUp = delta > 0;
  return (
    <span className={`text-[10px] font-bold ${isUp ? "text-emerald-500" : "text-red-500"}`}>
      {isUp ? "+" : ""}{delta}
    </span>
  );
}

export function GenreTrendSection({ genres }: { genres: GenreTrend[] }) {
  const [expanded, setExpanded] = useState(false);
  if (!genres || genres.length === 0) return null;

  const maxCount = Math.max(...genres.map((g) => g.current_count), 1);
  const displayGenres = expanded ? genres : genres.slice(0, 8);

  return (
    <div className="rounded-xl bg-card border border-border/50 shadow-sm overflow-hidden">
      <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: `1px solid ${RV}15` }}>
        <h3 className="text-xs font-bold text-foreground flex items-center gap-1.5">
          <span>🎭</span>
          장르 트렌드
        </h3>
        <span className="text-[10px] text-muted-foreground">vs 7일 전</span>
      </div>

      <div className="px-4 py-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2">
          {displayGenres.map((g) => (
            <div key={g.genre_kr} className="flex items-center gap-2">
              {/* 장르명 */}
              <span className="text-xs font-medium w-16 shrink-0 truncate">{g.genre_kr}</span>

              {/* 바 */}
              <div className="flex-1 h-4 bg-muted/40 rounded-full overflow-hidden relative">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.max((g.current_count / maxCount) * 100, 4)}%`,
                    background: g.riverse_count > 0
                      ? `linear-gradient(90deg, ${RV} ${(g.riverse_count / g.current_count) * 100}%, #94A3B8 0%)`
                      : "#94A3B8",
                  }}
                />
                {/* 카운트 표시 (바 위) */}
                <span className="absolute right-1.5 top-0 h-full flex items-center text-[10px] font-mono text-foreground/70">
                  {g.current_count}
                </span>
              </div>

              {/* 델타 */}
              <DeltaBadge delta={g.delta} />

              {/* 리버스 수 */}
              {g.riverse_count > 0 && (
                <span
                  className="text-[9px] px-1 py-0.5 rounded font-semibold shrink-0"
                  style={{ backgroundColor: RV_LIGHT, color: RV }}
                >
                  RV {g.riverse_count}
                </span>
              )}
            </div>
          ))}
        </div>

        {genres.length > 8 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-2 text-[11px] font-medium cursor-pointer transition-colors"
            style={{ color: RV }}
          >
            {expanded ? "접기" : `+${genres.length - 8}개 더 보기`}
          </button>
        )}
      </div>
    </div>
  );
}
