"use client";

import { LineChart, Line, YAxis, ResponsiveContainer } from "recharts";
import type { SparklinePoint } from "@/lib/trend-report";

interface MiniSparklineProps {
  data: SparklinePoint[];
  color?: string;
  width?: number;
  height?: number;
}

export function MiniSparkline({
  data,
  color = "#0D3B70",
  width = 100,
  height = 24,
}: MiniSparklineProps) {
  if (!data || data.length < 2) return null;

  return (
    <div className="shrink-0" style={{ width, height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <YAxis hide reversed domain={["dataMin - 2", "dataMax + 2"]} />
          <Line
            type="monotone"
            dataKey="rank"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
