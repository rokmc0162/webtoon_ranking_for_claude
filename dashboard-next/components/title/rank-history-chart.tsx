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
import type { RankHistory, RankHistoryResponse } from "@/lib/types";
import { getPlatformById } from "@/lib/constants";

type DateRange = "7d" | "30d" | "90d" | "all";

interface RankHistoryChartProps {
  data: RankHistoryResponse;
  platform: string;
  platformColor: string;
}

export function RankHistoryChart({ data, platform, platformColor }: RankHistoryChartProps) {
  const [range, setRange] = useState<DateRange>("30d");

  const platformInfo = getPlatformById(platform);
  const genreLabel = data.genre
    ? platformInfo?.genres.find((g) => g.key === data.genre)?.label || data.genre
    : "";

  const hasGenre = data.genre && data.overall.some((h) => h.genre_rank !== null);

  // 날짜 범위 필터
  const filtered = useMemo(() => {
    if (range === "all") return data.overall;
    const days = range === "7d" ? 7 : range === "30d" ? 30 : 90;
    return data.overall.slice(-days);
  }, [data.overall, range]);

  const chartData = filtered.map((h) => ({
    date: h.date.substring(5),
    fullDate: h.date,
    rank: h.rank,
    genre_rank: h.genre_rank,
  }));

  const allRanks = filtered.flatMap((h) =>
    [h.rank, h.genre_rank].filter((r): r is number => r !== null)
  );
  const minRank = allRanks.length > 0 ? Math.min(...allRanks) : 1;
  const maxRank = allRanks.length > 0 ? Math.max(...allRanks) : 50;

  // 통계
  const overallRanks = filtered.map((h) => h.rank).filter((r): r is number => r !== null);
  const overallAvg = overallRanks.length > 0
    ? (overallRanks.reduce((a, b) => a + b, 0) / overallRanks.length).toFixed(1)
    : "-";
  const overallBest = overallRanks.length > 0 ? Math.min(...overallRanks) : "-";
  const overallWorst = overallRanks.length > 0 ? Math.max(...overallRanks) : "-";

  const genreRanks = filtered.map((h) => h.genre_rank).filter((r): r is number => r !== null);
  const genreAvg = genreRanks.length > 0
    ? (genreRanks.reduce((a, b) => a + b, 0) / genreRanks.length).toFixed(1)
    : "-";
  const genreBest = genreRanks.length > 0 ? Math.min(...genreRanks) : "-";

  const ranges: { key: DateRange; label: string }[] = [
    { key: "7d", label: "7일" },
    { key: "30d", label: "30일" },
    { key: "90d", label: "90일" },
    { key: "all", label: "전체" },
  ];

  if (data.overall.length === 0) {
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
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-bold">📊 랭킹 추이</h2>
        <div className="flex gap-1">
          {ranges.map((r) => (
            <button
              key={r.key}
              onClick={() => setRange(r.key)}
              className={`px-2.5 py-1 text-xs rounded-full transition-colors cursor-pointer ${
                range === r.key
                  ? "text-white font-medium"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
              style={range === r.key ? { backgroundColor: platformColor } : undefined}
            >
              {r.label}
            </button>
          ))}
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
                const label = name === "rank" ? "종합" : genreLabel;
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
            {hasGenre && (
              <Legend
                formatter={(value: string) => (value === "rank" ? "종합" : genreLabel)}
                wrapperStyle={{ fontSize: 12, paddingTop: 4 }}
              />
            )}
            <Line
              type="monotone"
              dataKey="rank"
              name="rank"
              stroke={platformColor}
              strokeWidth={2.5}
              dot={{ fill: platformColor, r: 4, strokeWidth: 2, stroke: "#fff" }}
              activeDot={{ r: 6, fill: platformColor }}
              connectNulls
            />
            {hasGenre && (
              <Line
                type="monotone"
                dataKey="genre_rank"
                name="genre_rank"
                stroke={platformColor}
                strokeWidth={2}
                strokeDasharray="6 3"
                strokeOpacity={0.5}
                dot={{ fill: platformColor, r: 3, strokeWidth: 1, stroke: "#fff", opacity: 0.6 }}
                activeDot={{ r: 5, fill: platformColor, opacity: 0.7 }}
                connectNulls
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 통계 카드 */}
      <div className={`grid gap-3 mt-4 ${hasGenre ? "grid-cols-2" : "grid-cols-4"}`}>
        {hasGenre ? (
          <>
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-xs font-medium text-muted-foreground mb-2">종합 순위</div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="text-[10px] text-muted-foreground">최고</div>
                  <div className="text-base font-bold">{overallBest}위</div>
                </div>
                <div>
                  <div className="text-[10px] text-muted-foreground">평균</div>
                  <div className="text-base font-bold">{overallAvg}위</div>
                </div>
                <div>
                  <div className="text-[10px] text-muted-foreground">데이터</div>
                  <div className="text-base font-bold">{overallRanks.length}일</div>
                </div>
              </div>
            </div>
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-xs font-medium text-muted-foreground mb-2">{genreLabel} 순위</div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="text-[10px] text-muted-foreground">최고</div>
                  <div className="text-base font-bold">{genreBest}위</div>
                </div>
                <div>
                  <div className="text-[10px] text-muted-foreground">평균</div>
                  <div className="text-base font-bold">{genreAvg}위</div>
                </div>
                <div>
                  <div className="text-[10px] text-muted-foreground">데이터</div>
                  <div className="text-base font-bold">{genreRanks.length}일</div>
                </div>
              </div>
            </div>
          </>
        ) : (
          <>
            {[
              { label: "최고 순위", value: `${overallBest}위` },
              { label: "최저 순위", value: `${overallWorst}위` },
              { label: "평균 순위", value: `${overallAvg}위` },
              { label: "데이터", value: `${overallRanks.length}일` },
            ].map((stat) => (
              <div key={stat.label} className="text-center p-2.5 bg-muted rounded-lg">
                <div className="text-xs text-muted-foreground mb-0.5">{stat.label}</div>
                <div className="text-lg font-bold text-foreground">{stat.value}</div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
