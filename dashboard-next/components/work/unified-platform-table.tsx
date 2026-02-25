"use client";

import type { PlatformWorkEntry } from "@/lib/types";

interface UnifiedPlatformTableProps {
  platforms: PlatformWorkEntry[];
}

function formatDate(d: string | null): string {
  if (!d) return "-";
  return d.split("T")[0];
}

export function UnifiedPlatformTable({ platforms }: UnifiedPlatformTableProps) {
  if (platforms.length === 0) return null;

  return (
    <div className="bg-card rounded-xl border p-4 sm:p-6">
      <h2 className="text-base font-bold mb-4">📡 플랫폼별 상세 정보</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              <th className="text-left py-2 px-2 text-xs font-medium text-muted-foreground">플랫폼</th>
              <th className="text-center py-2 px-2 text-xs font-medium text-muted-foreground">최고순위</th>
              <th className="text-center py-2 px-2 text-xs font-medium text-muted-foreground">최근순위</th>
              <th className="text-center py-2 px-2 text-xs font-medium text-muted-foreground">평점</th>
              <th className="text-center py-2 px-2 text-xs font-medium text-muted-foreground">리뷰수</th>
              <th className="text-center py-2 px-2 text-xs font-medium text-muted-foreground hidden sm:table-cell">추적기간</th>
              <th className="text-center py-2 px-2 text-xs font-medium text-muted-foreground">링크</th>
            </tr>
          </thead>
          <tbody>
            {platforms.map((p) => (
              <tr key={p.platform} className="border-b last:border-0 hover:bg-muted/30">
                <td className="py-2 px-2">
                  <span
                    className="font-medium text-xs px-2 py-0.5 rounded-full text-white"
                    style={{ backgroundColor: p.platform_color }}
                  >
                    {p.platform_name}
                  </span>
                  <div className="text-[10px] text-muted-foreground mt-0.5 truncate max-w-[120px]">
                    {p.title}
                  </div>
                </td>
                <td className="py-2 px-2 text-center font-medium">
                  {p.best_rank != null ? `${p.best_rank}위` : "-"}
                </td>
                <td className="py-2 px-2 text-center">
                  {p.latest_rank != null ? (
                    <span>
                      {p.latest_rank}위
                      {p.latest_date && (
                        <span className="text-xs text-muted-foreground ml-1">
                          ({p.latest_date.substring(5)})
                        </span>
                      )}
                    </span>
                  ) : (
                    "-"
                  )}
                </td>
                <td className="py-2 px-2 text-center">
                  {p.rating != null ? p.rating.toFixed(1) : p.hearts != null ? `❤️${p.hearts.toLocaleString()}` : "-"}
                </td>
                <td className="py-2 px-2 text-center">
                  {p.review_count != null ? p.review_count.toLocaleString() : "-"}
                </td>
                <td className="py-2 px-2 text-center text-xs text-muted-foreground hidden sm:table-cell">
                  {formatDate(p.first_seen_date)} ~ {formatDate(p.last_seen_date)}
                </td>
                <td className="py-2 px-2 text-center">
                  {p.url && (
                    <a
                      href={p.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-500 hover:underline text-xs"
                    >
                      🔗
                    </a>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
