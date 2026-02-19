"use client";

import { useEffect, useState } from "react";
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
  Legend,
} from "recharts";
import type { RankHistory, RankHistoryResponse } from "@/lib/types";
import { getPlatformById } from "@/lib/constants";

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
  const [history, setHistory] = useState<RankHistory[]>([]);
  const [genre, setGenre] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !title) return;
    setLoading(true);
    fetch(
      `/api/history?title=${encodeURIComponent(title)}&platform=${encodeURIComponent(platform)}`
    )
      .then((res) => res.json())
      .then((data: RankHistoryResponse) => {
        setHistory(data.overall);
        setGenre(data.genre);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [open, title, platform]);

  // 장르 한국어 라벨
  const platformInfo = getPlatformById(platform);
  const genreLabel = genre
    ? platformInfo?.genres.find((g) => g.key === genre)?.label || genre
    : "";

  const hasGenre = genre && history.some((h) => h.genre_rank !== null);

  const chartData = history.map((h) => ({
    date: h.date.substring(5), // MM-DD
    fullDate: h.date,
    rank: h.rank,
    genre_rank: h.genre_rank,
  }));

  // 순위 범위 계산 (종합 + 장르 모두 고려)
  const allRanks = history.flatMap((h) =>
    [h.rank, h.genre_rank].filter((r): r is number => r !== null)
  );
  const minRank = allRanks.length > 0 ? Math.min(...allRanks) : 1;
  const maxRank = allRanks.length > 0 ? Math.max(...allRanks) : 50;

  // 종합 통계
  const overallRanks = history.map((h) => h.rank).filter((r): r is number => r !== null);
  const overallAvg =
    overallRanks.length > 0
      ? (overallRanks.reduce((a, b) => a + b, 0) / overallRanks.length).toFixed(1)
      : "-";
  const overallBest = overallRanks.length > 0 ? Math.min(...overallRanks) : "-";

  // 장르 통계
  const genreRanks = history.map((h) => h.genre_rank).filter((r): r is number => r !== null);
  const genreAvg =
    genreRanks.length > 0
      ? (genreRanks.reduce((a, b) => a + b, 0) / genreRanks.length).toFixed(1)
      : "-";
  const genreBest = genreRanks.length > 0 ? Math.min(...genreRanks) : "-";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[720px]">
        <DialogHeader>
          <DialogTitle className="text-lg">📈 {title}</DialogTitle>
          {titleKr && (
            <DialogDescription>{titleKr}</DialogDescription>
          )}
        </DialogHeader>

        {loading ? (
          <div className="h-[300px] flex items-center justify-center text-muted-foreground">
            로딩 중...
          </div>
        ) : history.length === 0 ? (
          <div className="h-[300px] flex items-center justify-center text-muted-foreground">
            히스토리 데이터가 없습니다.
          </div>
        ) : (
          <>
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
                    domain={[
                      Math.max(1, minRank - 2),
                      maxRank + 2,
                    ]}
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
                      formatter={(value: string) => {
                        if (value === "rank") return "종합";
                        return genreLabel;
                      }}
                      wrapperStyle={{ fontSize: 12, paddingTop: 4 }}
                    />
                  )}
                  {/* 종합 순위 - 실선 */}
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
                  {/* 장르 순위 - 점선 */}
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
            <div className={`grid gap-3 ${hasGenre ? "grid-cols-2" : "grid-cols-4"}`}>
              {hasGenre ? (
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
                        <div className="text-[10px] text-muted-foreground">데이터</div>
                        <div className="text-base font-bold">{overallRanks.length}일</div>
                      </div>
                    </div>
                  </div>
                  {/* 장르 통계 */}
                  <div className="p-3 bg-muted rounded-lg">
                    <div className="text-xs font-medium text-muted-foreground mb-2">
                      {genreLabel} 순위
                    </div>
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
                /* 종합만 있는 경우 기존 레이아웃 */
                <>
                  {[
                    { label: "최고 순위", value: `${overallBest}위` },
                    { label: "최저 순위", value: `${overallRanks.length > 0 ? Math.max(...overallRanks) : "-"}위` },
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
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
