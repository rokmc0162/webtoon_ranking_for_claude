"use client";

import type { KpiMetrics } from "@/lib/trend-report";

const RV = "#0D3B70";

function DeltaIndicator({ value, inverted = false }: { value: number; inverted?: boolean }) {
  if (value === 0) return <span className="text-muted-foreground text-xs">—</span>;

  // inverted: 낮아지면 좋은 지표(순위)에서 value가 음수면 개선
  const isGood = inverted ? value < 0 : value > 0;
  const displayValue = inverted ? Math.abs(value) : Math.abs(value);
  const arrow = (inverted ? value < 0 : value > 0) ? "▲" : "▼";
  const color = isGood ? "text-emerald-500" : "text-red-500";

  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-bold ${color}`}>
      {arrow} {displayValue % 1 !== 0 ? displayValue.toFixed(1) : displayValue}
    </span>
  );
}

interface KpiCardProps {
  label: string;
  value: number;
  unit?: string;
  delta: number;
  inverted?: boolean;
  icon: string;
}

function KpiCard({ label, value, unit = "", delta, inverted = false, icon }: KpiCardProps) {
  return (
    <div className="bg-card rounded-xl border border-border/50 p-3 sm:p-4 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center gap-1.5 mb-1">
        <span className="text-sm">{icon}</span>
        <span className="text-[11px] text-muted-foreground font-medium">{label}</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-xl sm:text-2xl font-bold" style={{ color: RV }}>
          {value % 1 !== 0 ? value.toFixed(1) : value}
          {unit && <span className="text-sm font-normal ml-0.5">{unit}</span>}
        </span>
        <DeltaIndicator value={delta} inverted={inverted} />
      </div>
      <div className="text-[10px] text-muted-foreground mt-0.5">vs 7일 전</div>
    </div>
  );
}

export function TrendKpiRow({ kpi }: { kpi: KpiMetrics }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-3">
      <KpiCard
        label="랭킹 진입 수"
        value={kpi.riverse_in_rankings}
        unit="건"
        delta={kpi.riverse_in_rankings_delta}
        icon="📈"
      />
      <KpiCard
        label="평균 순위"
        value={kpi.riverse_avg_rank}
        unit="위"
        delta={kpi.riverse_avg_rank_delta}
        inverted
        icon="🎯"
      />
      <KpiCard
        label="TOP 3 수"
        value={kpi.riverse_top3_count}
        unit="건"
        delta={kpi.riverse_top3_delta}
        icon="🏆"
      />
      <KpiCard
        label="전체 점유율"
        value={kpi.riverse_share_pct}
        unit="%"
        delta={kpi.riverse_share_pct_delta}
        icon="📊"
      />
    </div>
  );
}
