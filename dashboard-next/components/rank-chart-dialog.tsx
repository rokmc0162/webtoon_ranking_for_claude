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
  ReferenceLine,
} from "recharts";
import type { RankHistory } from "@/lib/types";

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
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !title) return;
    setLoading(true);
    fetch(
      `/api/history?title=${encodeURIComponent(title)}&platform=${encodeURIComponent(platform)}`
    )
      .then((res) => res.json())
      .then((data) => {
        setHistory(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [open, title, platform]);

  const chartData = history.map((h) => ({
    date: h.date.substring(5), // MM-DD
    fullDate: h.date,
    rank: h.rank,
  }));

  const ranks = history.map((h) => h.rank);
  const minRank = ranks.length > 0 ? Math.min(...ranks) : 1;
  const maxRank = ranks.length > 0 ? Math.max(...ranks) : 50;
  const avgRank =
    ranks.length > 0
      ? (ranks.reduce((a, b) => a + b, 0) / ranks.length).toFixed(1)
      : "-";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[680px]">
        <DialogHeader>
          <DialogTitle className="text-lg">📈 {title}</DialogTitle>
          {titleKr && (
            <DialogDescription>{titleKr}</DialogDescription>
          )}
        </DialogHeader>

        {loading ? (
          <div className="h-[280px] flex items-center justify-center text-muted-foreground">
            로딩 중...
          </div>
        ) : history.length === 0 ? (
          <div className="h-[280px] flex items-center justify-center text-muted-foreground">
            히스토리 데이터가 없습니다.
          </div>
        ) : (
          <>
            <div className="h-[280px] w-full">
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
                    formatter={(value: any) => [`${value}위`, "순위"]}
                    labelFormatter={(_label, payload) => {
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      const item = (payload as any)?.[0]?.payload;
                      return item?.fullDate || _label;
                    }}
                    contentStyle={{
                      borderRadius: "8px",
                      border: "1px solid #E5E7EB",
                      boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                    }}
                  />
                  <ReferenceLine y={minRank} stroke={platformColor} strokeDasharray="5 5" opacity={0.3} />
                  <Line
                    type="monotone"
                    dataKey="rank"
                    stroke={platformColor}
                    strokeWidth={2.5}
                    dot={{ fill: platformColor, r: 4, strokeWidth: 2, stroke: "#fff" }}
                    activeDot={{ r: 6, fill: platformColor }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="grid grid-cols-4 gap-3">
              {[
                { label: "최고 순위", value: `${minRank}위` },
                { label: "최저 순위", value: `${maxRank}위` },
                { label: "평균 순위", value: `${avgRank}위` },
                { label: "데이터", value: `${history.length}일` },
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
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
