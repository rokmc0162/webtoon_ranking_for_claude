"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { RankHistoryResponse } from "@/lib/types";
import { GENRE_COLORS } from "@/lib/constants";

interface RankChartDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  titleKr: string;
  platform: string;
  platformColor: string;
}

export function RankChartDialog({
  open,
  onOpenChange,
  title,
  titleKr,
  platform,
  platformColor,
}: RankChartDialogProps) {
  const [data, setData] = useState<RankHistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [hiddenLines, setHiddenLines] = useState<Set<string>>(new Set());

  const toggleLine = useCallback((key: string) => {
    setHiddenLines((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  useEffect(() => {
    if (!open || !title) return;
    setLoading(true);
    setHiddenLines(new Set());
    fetch(
      `/api/history?title=${encodeURIComponent(title)}&platform=${encodeURIComponent(platform)}`
    )
      .then((res) => res.json())
      .then((resp: RankHistoryResponse) => {
        setData(resp);
        // 2번째 이후 장르는 초기 숨김
        const initHidden = new Set<string>();
        resp.genres.forEach((g, i) => {
          if (i >= 1) initHidden.add(`genre:${g.sub_category}`);
        });
        setHiddenLines(initHidden);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [open, title, platform]);

  if (!data) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-[720px]">
          <DialogHeader>
            <DialogTitle className="text-lg">📈 {title}</DialogTitle>
            {titleKr && <DialogDescription>{titleKr}</DialogDescription>}
          </DialogHeader>
          <div className="h-[300px] flex items-center justify-center text-muted-foreground">
            {loading ? "로딩 중..." : "데이터가 없습니다."}
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  const hasGenres = data.genres.length > 0;

  // 장르별 데이터 맵
  const genreMaps: Record<string, Record<string, number>> = {};
  for (const g of data.genres) {
    genreMaps[g.sub_category] = {};
    for (const rh of g.history) {
      genreMaps[g.sub_category][rh.date] = rh.rank;
    }
  }

  // 모든 날짜 수집
  const dateSet = new Set<string>();
  for (const h of data.overall) dateSet.add(h.date);
  for (const g of data.genres) {
    if (hiddenLines.has(`genre:${g.sub_category}`)) continue;
    for (const rh of g.history) dateSet.add(rh.date);
  }

  const overallMap: Record<string, number> = {};
  for (const h of data.overall) {
    if (h.rank !== null) overallMap[h.date] = h.rank;
  }

  const chartData = Array.from(dateSet)
    .sort()
    .map((date) => {
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
      return entry;
    });

  // 순위 범위
  const allRanks: number[] = [];
  for (const d of chartData) {
    for (const [key, val] of Object.entries(d)) {
      if (key === "date" || key === "fullDate") continue;
      if (typeof val === "number") allRanks.push(val);
    }
  }
  const minRank = allRanks.length > 0 ? Math.min(...allRanks) : 1;
  const maxRank = allRanks.length > 0 ? Math.max(...allRanks) : 50;

  // 통계
  const overallRanks = data.overall
    .map((h) => h.rank)
    .filter((r): r is number => r !== null);
  const overallAvg =
    overallRanks.length > 0
      ? (overallRanks.reduce((a, b) => a + b, 0) / overallRanks.length).toFixed(1)
      : "-";
  const overallBest = overallRanks.length > 0 ? Math.min(...overallRanks) : "-";

  // 장르 이름 맵
  const genreNameMap: Record<string, string> = {};
  data.genres.forEach((g) => {
    genreNameMap[`genre_${g.sub_category}`] = g.label;
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[720px]">
        <DialogHeader>
          <DialogTitle className="text-lg">📈 {title}</DialogTitle>
          {titleKr && <DialogDescription>{titleKr}</DialogDescription>}
        </DialogHeader>

        {loading ? (
          <div className="h-[300px] flex items-center justify-center text-muted-foreground">
            로딩 중...
          </div>
        ) : data.overall.length === 0 ? (
          <div className="h-[300px] flex items-center justify-center text-muted-foreground">
            히스토리 데이터가 없습니다.
          </div>
        ) : (
          <>
            {/* 토글 칩 레전드 */}
            {hasGenres && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                <button
                  onClick={() => toggleLine("overall")}
                  className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-xs rounded-full border transition-all cursor-pointer ${
                    hiddenLines.has("overall")
                      ? "bg-muted text-muted-foreground opacity-50 line-through border-muted"
                      : "font-medium"
                  }`}
                  style={
                    !hiddenLines.has("overall")
                      ? { borderColor: platformColor, backgroundColor: `${platformColor}15`, color: platformColor }
                      : undefined
                  }
                >
                  <span className="w-3 h-0.5 rounded-full inline-block" style={{ backgroundColor: platformColor }} />
                  종합
                </button>
                {data.genres.map((g, i) => {
                  const color = GENRE_COLORS[i % GENRE_COLORS.length];
                  const hidden = hiddenLines.has(`genre:${g.sub_category}`);
                  return (
                    <button
                      key={g.sub_category}
                      onClick={() => toggleLine(`genre:${g.sub_category}`)}
                      className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-xs rounded-full border transition-all cursor-pointer ${
                        hidden ? "bg-muted text-muted-foreground opacity-50 line-through border-muted" : "font-medium"
                      }`}
                      style={!hidden ? { borderColor: color, backgroundColor: `${color}15`, color } : undefined}
                    >
                      <span className="w-3 h-0 inline-block" style={{ borderTop: `2px dashed ${color}` }} />
                      {g.label}
                    </button>
                  );
                })}
              </div>
            )}

            <div className="h-[300px] w-full">
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
                      if (name === "rank") return [`${value}위`, "종합"];
                      if (genreNameMap[name]) return [`${value}위`, genreNameMap[name]];
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
                      dot={{ fill: platformColor, r: 4, strokeWidth: 2, stroke: "#fff" }}
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
                        dot={{ fill: color, r: 3, strokeWidth: 1, stroke: "#fff" }}
                        activeDot={{ r: 5, fill: color }}
                        connectNulls
                      />
                    );
                  })}
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* 통계 카드 */}
            <div className={`grid gap-3 ${hasGenres ? "grid-cols-2" : "grid-cols-4"}`}>
              {hasGenres ? (
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
                  {(() => {
                    const topGenre = data.genres[0];
                    if (!topGenre) return null;
                    const gRanks = topGenre.history.map((h) => h.rank);
                    const gBest = gRanks.length > 0 ? Math.min(...gRanks) : "-";
                    const gAvg = gRanks.length > 0
                      ? (gRanks.reduce((a, b) => a + b, 0) / gRanks.length).toFixed(1) : "-";
                    return (
                      <div className="p-3 bg-muted rounded-lg">
                        <div className="text-xs font-medium text-muted-foreground mb-2">{topGenre.label} 순위</div>
                        <div className="grid grid-cols-3 gap-2 text-center">
                          <div>
                            <div className="text-[10px] text-muted-foreground">최고</div>
                            <div className="text-base font-bold">{gBest}위</div>
                          </div>
                          <div>
                            <div className="text-[10px] text-muted-foreground">평균</div>
                            <div className="text-base font-bold">{gAvg}위</div>
                          </div>
                          <div>
                            <div className="text-[10px] text-muted-foreground">데이터</div>
                            <div className="text-base font-bold">{gRanks.length}일</div>
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
                    { label: "최저 순위", value: `${overallRanks.length > 0 ? Math.max(...overallRanks) : "-"}위` },
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
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
