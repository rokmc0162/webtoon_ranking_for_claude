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
import type { RankHistoryResponse, CrossPlatformEntry } from "@/lib/types";
import { getPlatformById, GENRE_COLORS } from "@/lib/constants";

type DateRange = "7d" | "30d" | "90d" | "all";

interface RankHistoryChartProps {
  data: RankHistoryResponse;
  platform: string;
  platformColor: string;
  crossPlatform?: CrossPlatformEntry[];
}

export function RankHistoryChart({
  data,
  platform,
  platformColor,
  crossPlatform = [],
}: RankHistoryChartProps) {
  const [range, setRange] = useState<DateRange>("30d");
  const [showCross, setShowCross] = useState(false);

  // 초기 숨김: 2번째 이후 장르 + 크로스플랫폼
  const [hiddenLines, setHiddenLines] = useState<Set<string>>(() => {
    const initial = new Set<string>();
    data.genres.forEach((g, i) => {
      if (i >= 1) initial.add(`genre:${g.sub_category}`);
    });
    return initial;
  });

  const toggleLine = useCallback((key: string) => {
    setHiddenLines((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const platformInfo = getPlatformById(platform);
  const platformName = platformInfo?.name || platform;

  const crossWithHistory = crossPlatform.filter(
    (cp) => cp.rank_history && cp.rank_history.length > 0
  );
  const hasCross = crossWithHistory.length > 0;
  const hasGenres = data.genres.length > 0;

  // 날짜 범위 필터
  const filtered = useMemo(() => {
    if (range === "all") return data.overall;
    const days = range === "7d" ? 7 : range === "30d" ? 30 : 90;
    return data.overall.slice(-days);
  }, [data.overall, range]);

  // 차트 데이터 생성
  const chartData = useMemo(() => {
    const dateSet = new Set<string>();
    for (const h of filtered) dateSet.add(h.date);

    // 장르 날짜 수집
    for (const g of data.genres) {
      if (hiddenLines.has(`genre:${g.sub_category}`)) continue;
      for (const rh of g.history) dateSet.add(rh.date);
    }

    // 크로스플랫폼 날짜
    if (showCross) {
      for (const cp of crossWithHistory) {
        if (hiddenLines.has(`cross:${cp.platform}`)) continue;
        for (const rh of cp.rank_history) dateSet.add(rh.date);
      }
    }

    const dates = Array.from(dateSet).sort();
    const days =
      range === "7d" ? 7 : range === "30d" ? 30 : range === "90d" ? 90 : Infinity;
    const sliced = days === Infinity ? dates : dates.slice(-days);

    // 종합 데이터 맵
    const overallMap: Record<string, number> = {};
    for (const h of data.overall) overallMap[h.date] = h.rank ?? 0;

    // 장르별 데이터 맵
    const genreMaps: Record<string, Record<string, number>> = {};
    for (const g of data.genres) {
      genreMaps[g.sub_category] = {};
      for (const rh of g.history) {
        genreMaps[g.sub_category][rh.date] = rh.rank;
      }
    }

    // 크로스플랫폼 데이터 맵
    const crossMaps: Record<string, Record<string, number>> = {};
    for (const cp of crossWithHistory) {
      crossMaps[cp.platform] = {};
      for (const rh of cp.rank_history) {
        crossMaps[cp.platform][rh.date] = rh.rank;
      }
    }

    return sliced.map((date) => {
      const entry: Record<string, string | number | null> = {
        date: date.substring(5),
        fullDate: date,
      };

      if (!hiddenLines.has("overall")) {
        entry.rank = overallMap[date] ?? null;
      }

      for (const g of data.genres) {
        if (!hiddenLines.has(`genre:${g.sub_category}`)) {
          entry[`genre_${g.sub_category}`] =
            genreMaps[g.sub_category]?.[date] ?? null;
        }
      }

      if (showCross) {
        for (const cp of crossWithHistory) {
          if (!hiddenLines.has(`cross:${cp.platform}`)) {
            entry[`cross_${cp.platform}`] =
              crossMaps[cp.platform]?.[date] ?? null;
          }
        }
      }
      return entry;
    });
  }, [filtered, data, crossWithHistory, showCross, range, hiddenLines]);

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

  // 통계
  const overallRanks = filtered
    .map((h) => h.rank)
    .filter((r): r is number => r !== null);
  const overallAvg =
    overallRanks.length > 0
      ? (overallRanks.reduce((a, b) => a + b, 0) / overallRanks.length).toFixed(1)
      : "-";
  const overallBest = overallRanks.length > 0 ? Math.min(...overallRanks) : "-";
  const overallWorst = overallRanks.length > 0 ? Math.max(...overallRanks) : "-";

  const ranges: { key: DateRange; label: string }[] = [
    { key: "7d", label: "7일" },
    { key: "30d", label: "30일" },
    { key: "90d", label: "90일" },
    { key: "all", label: "전체" },
  ];

  // 크로스 플랫폼 이름/색상 맵
  const crossNameMap: Record<string, string> = {};
  const crossColorMap: Record<string, string> = {};
  for (const cp of crossWithHistory) {
    crossNameMap[`cross_${cp.platform}`] = cp.platform_name;
    crossColorMap[`cross_${cp.platform}`] = cp.platform_color;
  }

  // 장르 이름 맵 (툴팁용)
  const genreNameMap: Record<string, string> = {};
  const genreColorMap: Record<string, string> = {};
  data.genres.forEach((g, i) => {
    genreNameMap[`genre_${g.sub_category}`] = g.label;
    genreColorMap[`genre_${g.sub_category}`] = GENRE_COLORS[i % GENRE_COLORS.length];
  });

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
      {/* 헤더: 제목 + 기간 토글 */}
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <h2 className="text-base font-bold">📊 랭킹 추이</h2>
        <div className="flex items-center gap-2">
          {hasCross && (
            <button
              onClick={() => setShowCross(!showCross)}
              className={`px-2.5 py-1 text-xs rounded-full transition-colors cursor-pointer ${
                showCross
                  ? "bg-blue-500 text-white font-medium"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              크로스 플랫폼
            </button>
          )}
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
      </div>

      {/* 커스텀 레전드: 토글 가능한 칩 */}
      {(hasGenres || (showCross && hasCross)) && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {/* 종합 칩 */}
          <button
            onClick={() => toggleLine("overall")}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-full border transition-all cursor-pointer ${
              hiddenLines.has("overall")
                ? "bg-muted text-muted-foreground opacity-50 line-through border-muted"
                : "font-medium"
            }`}
            style={
              !hiddenLines.has("overall")
                ? {
                    borderColor: platformColor,
                    backgroundColor: `${platformColor}15`,
                    color: platformColor,
                  }
                : undefined
            }
          >
            <span
              className="w-4 h-0.5 rounded-full inline-block"
              style={{ backgroundColor: platformColor }}
            />
            {platformName}
          </button>

          {/* 장르 칩들 */}
          {data.genres.map((g, i) => {
            const color = GENRE_COLORS[i % GENRE_COLORS.length];
            const hidden = hiddenLines.has(`genre:${g.sub_category}`);
            return (
              <button
                key={g.sub_category}
                onClick={() => toggleLine(`genre:${g.sub_category}`)}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-full border transition-all cursor-pointer ${
                  hidden
                    ? "bg-muted text-muted-foreground opacity-50 line-through border-muted"
                    : "font-medium"
                }`}
                style={
                  !hidden
                    ? {
                        borderColor: color,
                        backgroundColor: `${color}15`,
                        color: color,
                      }
                    : undefined
                }
              >
                <span
                  className="w-4 h-0 inline-block"
                  style={{ borderTop: `2px dashed ${color}` }}
                />
                {g.label}
              </button>
            );
          })}

          {/* 크로스 플랫폼 칩들 */}
          {showCross &&
            crossWithHistory.map((cp) => {
              const hidden = hiddenLines.has(`cross:${cp.platform}`);
              return (
                <button
                  key={`cross_${cp.platform}`}
                  onClick={() => toggleLine(`cross:${cp.platform}`)}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-full border transition-all cursor-pointer ${
                    hidden
                      ? "bg-muted text-muted-foreground opacity-50 line-through border-muted"
                      : "font-medium"
                  }`}
                  style={
                    !hidden
                      ? {
                          borderColor: cp.platform_color,
                          backgroundColor: `${cp.platform_color}15`,
                          color: cp.platform_color,
                        }
                      : undefined
                  }
                >
                  <span
                    className="w-4 h-0 inline-block"
                    style={{ borderTop: `2px dashed ${cp.platform_color}` }}
                  />
                  {cp.platform_name}
                </button>
              );
            })}
        </div>
      )}

      {/* 차트 */}
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
                if (name === "rank") return [`${value}위`, platformName];
                if (genreNameMap[name])
                  return [`${value}위`, genreNameMap[name]];
                if (crossNameMap[name])
                  return [`${value}위`, crossNameMap[name]];
                return [`${value}위`, name];
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
            {/* 종합 실선 */}
            {!hiddenLines.has("overall") && (
              <Line
                type="monotone"
                dataKey="rank"
                name="rank"
                stroke={platformColor}
                strokeWidth={2.5}
                dot={{
                  fill: platformColor,
                  r: 4,
                  strokeWidth: 2,
                  stroke: "#fff",
                }}
                activeDot={{ r: 6, fill: platformColor }}
                connectNulls
              />
            )}
            {/* 장르별 점선 */}
            {data.genres.map((g, i) => {
              if (hiddenLines.has(`genre:${g.sub_category}`)) return null;
              const color = GENRE_COLORS[i % GENRE_COLORS.length];
              return (
                <Line
                  key={`genre_${g.sub_category}`}
                  type="monotone"
                  dataKey={`genre_${g.sub_category}`}
                  name={`genre_${g.sub_category}`}
                  stroke={color}
                  strokeWidth={2}
                  strokeDasharray="6 3"
                  dot={{
                    fill: color,
                    r: 3,
                    strokeWidth: 1,
                    stroke: "#fff",
                  }}
                  activeDot={{ r: 5, fill: color }}
                  connectNulls
                />
              );
            })}
            {/* 크로스 플랫폼 점선 */}
            {showCross &&
              crossWithHistory.map((cp) => {
                if (hiddenLines.has(`cross:${cp.platform}`)) return null;
                return (
                  <Line
                    key={cp.platform}
                    type="monotone"
                    dataKey={`cross_${cp.platform}`}
                    name={`cross_${cp.platform}`}
                    stroke={cp.platform_color}
                    strokeWidth={2}
                    strokeDasharray="4 2"
                    dot={{
                      fill: cp.platform_color,
                      r: 3,
                      strokeWidth: 1,
                      stroke: "#fff",
                    }}
                    activeDot={{ r: 5, fill: cp.platform_color }}
                    connectNulls
                  />
                );
              })}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 통계 카드 */}
      <div
        className={`grid gap-3 mt-4 ${hasGenres ? "grid-cols-2" : "grid-cols-4"}`}
      >
        {hasGenres ? (
          <>
            {/* 종합 통계 */}
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-xs font-medium text-muted-foreground mb-2">
                종합 순위
              </div>
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
                  <div className="text-[10px] text-muted-foreground">
                    데이터
                  </div>
                  <div className="text-base font-bold">
                    {overallRanks.length}일
                  </div>
                </div>
              </div>
            </div>
            {/* 상위 1개 장르 통계 */}
            {(() => {
              const topGenre = data.genres[0];
              if (!topGenre) return null;
              const gRanks = topGenre.history.map((h) => h.rank);
              const gBest =
                gRanks.length > 0 ? Math.min(...gRanks) : "-";
              const gAvg =
                gRanks.length > 0
                  ? (
                      gRanks.reduce((a, b) => a + b, 0) / gRanks.length
                    ).toFixed(1)
                  : "-";
              return (
                <div className="p-3 bg-muted rounded-lg">
                  <div className="text-xs font-medium text-muted-foreground mb-2">
                    {topGenre.label} 순위
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div>
                      <div className="text-[10px] text-muted-foreground">
                        최고
                      </div>
                      <div className="text-base font-bold">{gBest}위</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-muted-foreground">
                        평균
                      </div>
                      <div className="text-base font-bold">{gAvg}위</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-muted-foreground">
                        데이터
                      </div>
                      <div className="text-base font-bold">
                        {gRanks.length}일
                      </div>
                    </div>
                  </div>
                </div>
              );
            })()}
          </>
        ) : (
          <>
            {[
              { label: "최고 순위", value: `${overallBest}위` },
              { label: "최저 순위", value: `${overallWorst}위` },
              { label: "평균 순위", value: `${overallAvg}위` },
              { label: "데이터", value: `${overallRanks.length}일` },
            ].map((stat) => (
              <div
                key={stat.label}
                className="text-center p-2.5 bg-muted rounded-lg"
              >
                <div className="text-xs text-muted-foreground mb-0.5">
                  {stat.label}
                </div>
                <div className="text-lg font-bold text-foreground">
                  {stat.value}
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
