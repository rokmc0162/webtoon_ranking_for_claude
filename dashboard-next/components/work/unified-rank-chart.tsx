"use client";

import { useState, useMemo, useCallback } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { PlatformWorkEntry } from "@/lib/types";
import { GENRE_COLORS } from "@/lib/constants";

type DateRange = "7d" | "30d" | "90d" | "all";

const DASH_PATTERNS = ["6 3", "4 4", "2 2", "8 2 2 2"];

interface UnifiedRankChartProps {
  platforms: PlatformWorkEntry[];
}

export function UnifiedRankChart({ platforms }: UnifiedRankChartProps) {
  const [range, setRange] = useState<DateRange>("30d");
  const [showGenre, setShowGenre] = useState(false);
  const [hiddenLines, setHiddenLines] = useState<Set<string>>(new Set());

  const toggleLine = useCallback((key: string) => {
    setHiddenLines((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  // 히스토리가 있는 플랫폼만
  const withHistory = platforms.filter((p) => p.rank_history.length > 0);
  const hasGenreData = platforms.some((p) => p.genre_histories.length > 0);

  // 차트 데이터 생성
  const chartData = useMemo(() => {
    const dateSet = new Set<string>();
    for (const p of withHistory) {
      if (hiddenLines.has(p.platform)) continue;
      for (const rh of p.rank_history) dateSet.add(rh.date);
      if (showGenre) {
        for (const gh of p.genre_histories) {
          if (hiddenLines.has(`${p.platform}:genre:${gh.sub_category}`)) continue;
          for (const rh of gh.history) dateSet.add(rh.date);
        }
      }
    }

    const dates = Array.from(dateSet).sort();
    const days =
      range === "7d" ? 7 : range === "30d" ? 30 : range === "90d" ? 90 : Infinity;
    const sliced = days === Infinity ? dates : dates.slice(-days);

    // 데이터 맵 생성
    const maps: Record<string, Record<string, number>> = {};
    const genreMaps: Record<string, Record<string, Record<string, number>>> = {};
    for (const p of withHistory) {
      maps[p.platform] = {};
      for (const rh of p.rank_history) {
        maps[p.platform][rh.date] = rh.rank;
      }
      if (showGenre) {
        genreMaps[p.platform] = {};
        for (const gh of p.genre_histories) {
          genreMaps[p.platform][gh.sub_category] = {};
          for (const rh of gh.history) {
            genreMaps[p.platform][gh.sub_category][rh.date] = rh.rank;
          }
        }
      }
    }

    return sliced.map((date) => {
      const entry: Record<string, string | number | null> = {
        date: date.substring(5),
        fullDate: date,
      };
      for (const p of withHistory) {
        if (!hiddenLines.has(p.platform)) {
          entry[p.platform] = maps[p.platform]?.[date] ?? null;
        }
        if (showGenre && genreMaps[p.platform]) {
          for (const gh of p.genre_histories) {
            const key = `${p.platform}_genre_${gh.sub_category}`;
            if (!hiddenLines.has(`${p.platform}:genre:${gh.sub_category}`)) {
              entry[key] =
                genreMaps[p.platform]?.[gh.sub_category]?.[date] ?? null;
            }
          }
        }
      }
      return entry;
    });
  }, [withHistory, showGenre, range, hiddenLines]);

  // Y축 범위
  const allRanks = useMemo(() => {
    const ranks: number[] = [];
    for (const d of chartData) {
      for (const [key, val] of Object.entries(d)) {
        if (key === "date" || key === "fullDate") continue;
        if (typeof val === "number") ranks.push(val);
      }
    }
    return ranks;
  }, [chartData]);

  const minRank = allRanks.length > 0 ? Math.min(...allRanks) : 1;
  const maxRank = allRanks.length > 0 ? Math.max(...allRanks) : 50;

  // 이름/색상 맵 (툴팁용)
  const nameMap: Record<string, string> = {};
  const colorMap: Record<string, string> = {};
  for (const p of withHistory) {
    nameMap[p.platform] = p.platform_name;
    colorMap[p.platform] = p.platform_color;
    for (const gh of p.genre_histories) {
      const key = `${p.platform}_genre_${gh.sub_category}`;
      nameMap[key] = `${p.platform_name} (${gh.label})`;
      colorMap[key] = p.platform_color;
    }
  }

  const ranges: { key: DateRange; label: string }[] = [
    { key: "7d", label: "7일" },
    { key: "30d", label: "30일" },
    { key: "90d", label: "90일" },
    { key: "all", label: "전체" },
  ];

  if (withHistory.length === 0) {
    return (
      <div className="bg-card rounded-xl border p-6">
        <h2 className="text-base font-bold mb-4">📊 랭킹 추이</h2>
        <div className="h-[200px] flex items-center justify-center text-muted-foreground">
          히스토리 데이터가 없습니다.
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-xl border p-4 sm:p-6">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <h2 className="text-base font-bold">📊 멀티 플랫폼 랭킹 추이</h2>
        <div className="flex items-center gap-2">
          {hasGenreData && (
            <button
              onClick={() => setShowGenre(!showGenre)}
              className={`px-2.5 py-1 text-xs rounded-full transition-colors cursor-pointer ${
                showGenre
                  ? "bg-blue-500 text-white font-medium"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              장르순위
            </button>
          )}
          <div className="flex gap-1">
            {ranges.map((r) => (
              <button
                key={r.key}
                onClick={() => setRange(r.key)}
                className={`px-2.5 py-1 text-xs rounded-full transition-colors cursor-pointer ${
                  range === r.key
                    ? "bg-blue-600 text-white font-medium"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 커스텀 레전드: 토글 가능한 칩 */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {withHistory.map((p) => (
          <span key={p.platform} className="contents">
            {/* 플랫폼 종합 칩 */}
            <button
              onClick={() => toggleLine(p.platform)}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-full border transition-all cursor-pointer ${
                hiddenLines.has(p.platform)
                  ? "bg-muted text-muted-foreground opacity-50 line-through border-muted"
                  : "font-medium"
              }`}
              style={
                !hiddenLines.has(p.platform)
                  ? {
                      borderColor: p.platform_color,
                      backgroundColor: `${p.platform_color}15`,
                      color: p.platform_color,
                    }
                  : undefined
              }
            >
              <span
                className="w-4 h-0.5 rounded-full inline-block"
                style={{ backgroundColor: p.platform_color }}
              />
              {p.platform_name}
            </button>

            {/* 장르 칩들 (showGenre일 때만) */}
            {showGenre &&
              p.genre_histories.map((gh, gi) => {
                const hidden = hiddenLines.has(
                  `${p.platform}:genre:${gh.sub_category}`
                );
                return (
                  <button
                    key={`${p.platform}:${gh.sub_category}`}
                    onClick={() =>
                      toggleLine(`${p.platform}:genre:${gh.sub_category}`)
                    }
                    className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-full border transition-all cursor-pointer ${
                      hidden
                        ? "bg-muted text-muted-foreground opacity-50 line-through border-muted"
                        : "font-medium"
                    }`}
                    style={
                      !hidden
                        ? {
                            borderColor: p.platform_color,
                            backgroundColor: `${p.platform_color}10`,
                            color: p.platform_color,
                            opacity: 0.8,
                          }
                        : undefined
                    }
                  >
                    <span
                      className="w-4 h-0 inline-block"
                      style={{
                        borderTop: `2px dashed ${GENRE_COLORS[gi % GENRE_COLORS.length]}`,
                      }}
                    />
                    {p.platform_name}({gh.label})
                  </button>
                );
              })}
          </span>
        ))}
      </div>

      <div className="h-[280px] sm:h-[320px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{ top: 10, right: 20, left: 10, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "#9CA3AF" }}
              axisLine={{ stroke: "#E5E7EB" }}
            />
            <YAxis
              reversed
              domain={[Math.max(1, minRank - 2), maxRank + 2]}
              tick={{ fontSize: 11, fill: "#9CA3AF" }}
              axisLine={{ stroke: "#E5E7EB" }}
              tickFormatter={(v) => `${v}위`}
            />
            <Tooltip
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={(value: any, name: any) => {
                const label = nameMap[name] || name;
                return [`${value}위`, label];
              }}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              labelFormatter={(_label: any, payload: any) => {
                const item = payload?.[0]?.payload;
                return item?.fullDate || _label;
              }}
              contentStyle={{
                borderRadius: "8px",
                border: "1px solid #E5E7EB",
                boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
              }}
            />
            {/* 종합 순위 실선 */}
            {withHistory.map((p) => {
              if (hiddenLines.has(p.platform)) return null;
              return (
                <Line
                  key={p.platform}
                  type="monotone"
                  dataKey={p.platform}
                  name={p.platform}
                  stroke={p.platform_color}
                  strokeWidth={2.5}
                  dot={{
                    fill: p.platform_color,
                    r: 3,
                    strokeWidth: 1,
                    stroke: "#fff",
                  }}
                  activeDot={{ r: 5, fill: p.platform_color }}
                  connectNulls
                />
              );
            })}
            {/* 장르 순위 점선 */}
            {showGenre &&
              withHistory.map((p) =>
                p.genre_histories.map((gh, gi) => {
                  if (
                    hiddenLines.has(
                      `${p.platform}:genre:${gh.sub_category}`
                    )
                  )
                    return null;
                  const dataKey = `${p.platform}_genre_${gh.sub_category}`;
                  return (
                    <Line
                      key={dataKey}
                      type="monotone"
                      dataKey={dataKey}
                      name={dataKey}
                      stroke={p.platform_color}
                      strokeWidth={1.5}
                      strokeDasharray={
                        DASH_PATTERNS[gi % DASH_PATTERNS.length]
                      }
                      strokeOpacity={0.5}
                      dot={{
                        fill: p.platform_color,
                        r: 2,
                        strokeWidth: 1,
                        stroke: "#fff",
                        opacity: 0.5,
                      }}
                      activeDot={{
                        r: 4,
                        fill: p.platform_color,
                        opacity: 0.7,
                      }}
                      connectNulls
                    />
                  );
                })
              )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 플랫폼별 통계 카드 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 mt-4">
        {withHistory.map((p) => {
          const ranks = p.rank_history.map((r) => r.rank);
          const best = ranks.length > 0 ? Math.min(...ranks) : null;
          const avg =
            ranks.length > 0
              ? (ranks.reduce((a, b) => a + b, 0) / ranks.length).toFixed(1)
              : "-";
          return (
            <div key={p.platform} className="p-2.5 bg-muted rounded-lg">
              <div className="flex items-center gap-1.5 mb-1">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: p.platform_color }}
                />
                <span className="text-xs font-medium truncate">
                  {p.platform_name}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-1 text-center">
                <div>
                  <div className="text-[10px] text-muted-foreground">최고</div>
                  <div className="text-sm font-bold">
                    {best != null ? `${best}위` : "-"}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-muted-foreground">평균</div>
                  <div className="text-sm font-bold">{avg}위</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
