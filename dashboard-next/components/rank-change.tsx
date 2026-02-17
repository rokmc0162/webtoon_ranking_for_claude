"use client";

interface RankChangeProps {
  change: number;
}

export function RankChange({ change }: RankChangeProps) {
  if (change === 999) {
    return (
      <span className="inline-block bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full text-xs font-bold">
        NEW
      </span>
    );
  }

  if (change > 0) {
    return (
      <span className="text-red-500 font-semibold text-sm">
        ▲{change}
      </span>
    );
  }

  if (change < 0) {
    return (
      <span className="text-blue-500 font-semibold text-sm">
        ▼{Math.abs(change)}
      </span>
    );
  }

  return <span className="text-muted-foreground">—</span>;
}
