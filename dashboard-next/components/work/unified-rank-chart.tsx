"use client";

import { useState, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { PlatformWorkEntry } from "@/lib/types";

type DateRange = "7d" | "30d" | "90d" | "all";

interface UnifiedRankChartProps {
  platforms: PlatformWorkEntry[];
}

export function UnifiedRankChart({ platforms }: UnifiedRankChartProps) {
  const [range, setRange] = useState<DateRange>("30d");
  const [showGenre, setShowGenre] = useState(false);

  // 히스토리가 있는 플랫폼만
  const withHistory = platforms.filter((p) => p.rank_history.length > 0);
  const hasGenreData = platforms.some((p) => p.genre_rank_history.length > 0);

  // 차트 데이터 생성
  const chartData = useMemo(() => {
    const dateSet = new Set<string>();
    for (const p of withHistory) {
      for (const rh of p.rank_history) dateSet.add(rh.date);
      if (showGenre) {
        for (const rh of p.genre_rank_history) dateSet.add(rh.date);
      }
    }

    const dates = Array.from(dateSet).sort();
    const days = range === "7d" ? 7 : range === "30d" ? 30 : range === "90d" ? 90 : Infinity;
    const sliced = days === Infinity ? dates : dates.slice(-days);

    // 데이터 맵 생성
    const maps: Record<string, Record<string, number>> = {};
    const genreMaps: Record<string, Record<string, number>> = {};
    for (const p of withHistory) {
      maps[p.platform] = {};
      for (const rh of p.rank_history) {
        maps[p.platform][rh.date] = rh.rank;
      }
      if (showGenre && p.genre_rank_history.length > 0) {
        genreMaps[p.platform] = {};
        for (const rh of p.genre_rank_history) {
          genreMaps[p.platform][rh.date] = rh.rank;
        }
      }
    }

    return sliced.map((date) => {
      const entry: Record<string, string | number | null> = {
        date: date.substring(5),
        fullDate: date,
      };
      for (const p of withHistory) {
        entry[p.platform] = maps[p.platform]?.[date] ?? null;
        if (showGenre && genreMaps[p.platform]) {
          entry[`${p.platform}_genre`] = genreMaps[p.platform]?.[date] ?? null;
        }
      }
      return entry;
    });
  }, [withHistory, showGenre, range]);

  // Y축 범위
  const allRanks = useMemo(() => {
    const ranks: number[] = [];
    for (const d of chartData) {
      for (const p of withHistory) {
        const v = d[p.platform];
        if (typeof v === "number") ranks.push(v);
        if (showGenre) {
          const gv = d[`${p.platform}_genre`];
          if (typeof gv === "number") ranks.push(gv);
        }
      }
    }
    return ranks;
  }, [chartData, withHistory, showGenre]);

  const minRank = allRanks.length > 0 ? Math.min(...allRanks) : 1;
  const maxRank = allRanks.length > 0 ? Math.max(...allRanks) : 50;

  const nameMap: Record<string, string> = {};
  const colorMap: Record<string, string> = {};
  for (const p of withHistory) {
    nameMap[p.platform] = p.platform_name;
    colorMap[p.platform] = p.platform_color;
    if (p.genre_label) {
      nameMap[`${p.platform}_genre`] = `${p.platform_name} (${p.genre_label})`;
      colorMap[`${p.platform}_genre`] = p.platform_color;
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
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
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

      <div className="h-[280px] sm:h-[320px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
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
            <Legend
              formatter={(value: string) => nameMap[value] || value}
              wrapperStyle={{ fontSize: 12, paddingTop: 4 }}
            />
            {/* 종합 순위 실선 */}
            {withHistory.map((p) => (
              <Line
                key={p.platform}
                type="monotone"
                dataKey={p.platform}
                name={p.platform}
                stroke={p.platform_color}
                strokeWidth={2.5}
                dot={{ fill: p.platform_color, r: 3, strokeWidth: 1, stroke: "#fff" }}
                activeDot={{ r: 5, fill: p.platform_color }}
                connectNulls
              />
            ))}
            {/* 장르 순위 점선 */}
            {showGenre &&
              withHistory
                .filter((p) => p.genre_rank_history.length > 0)
                .map((p) => (
                  <Line
                    key={`${p.platform}_genre`}
                    type="monotone"
                    dataKey={`${p.platform}_genre`}
                    name={`${p.platform}_genre`}
                    stroke={p.platform_color}
                    strokeWidth={1.5}
                    strokeDasharray="6 3"
                    strokeOpacity={0.5}
                    dot={{ fill: p.platform_color, r: 2, strokeWidth: 1, stroke: "#fff", opacity: 0.5 }}
                    activeDot={{ r: 4, fill: p.platform_color, opacity: 0.7 }}
                    connectNulls
                  />
                ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 플랫폼별 통계 카드 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 mt-4">
        {withHistory.map((p) => {
          const ranks = p.rank_history.map((r) => r.rank);
          const best = ranks.length > 0 ? Math.min(...ranks) : null;
          const avg = ranks.length > 0
            ? (ranks.reduce((a, b) => a + b, 0) / ranks.length).toFixed(1)
            : "-";
          return (
            <div key={p.platform} className="p-2.5 bg-muted rounded-lg">
              <div className="flex items-center gap-1.5 mb-1">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: p.platform_color }}
                />
                <span className="text-xs font-medium truncate">{p.platform_name}</span>
              </div>
              <div className="grid grid-cols-2 gap-1 text-center">
                <div>
                  <div className="text-[10px] text-muted-foreground">최고</div>
                  <div className="text-sm font-bold">{best != null ? `${best}위` : "-"}</div>
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
