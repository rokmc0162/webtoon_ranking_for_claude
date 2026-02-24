"use client";

import type { CrossPlatformEntry } from "@/lib/types";
import { PLATFORMS } from "@/lib/constants";

interface CrossPlatformTableProps {
  entries: CrossPlatformEntry[];
  currentPlatform: string;
}

export function CrossPlatformTable({ entries, currentPlatform }: CrossPlatformTableProps) {
  if (entries.length === 0) return null;

  return (
    <div className="bg-card rounded-xl border p-4 sm:p-6">
      <h2 className="text-base font-bold mb-4">🔄 크로스 플랫폼 비교</h2>
      <p className="text-xs text-muted-foreground mb-3">
        동일 작품이 다른 플랫폼에서도 연재 중입니다.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              <th className="text-left py-2 px-2 text-xs font-medium text-muted-foreground">플랫폼</th>
              <th className="text-center py-2 px-2 text-xs font-medium text-muted-foreground">최고순위</th>
              <th className="text-center py-2 px-2 text-xs font-medium text-muted-foreground">최근순위</th>
              <th className="text-center py-2 px-2 text-xs font-medium text-muted-foreground">평점</th>
              <th className="text-center py-2 px-2 text-xs font-medium text-muted-foreground">리뷰수</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const pInfo = PLATFORMS.find((p) => p.id === entry.platform);
              return (
                <tr key={entry.platform} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="py-2 px-2">
                    <span
                      className="font-medium text-xs px-2 py-0.5 rounded-full text-white"
                      style={{ backgroundColor: pInfo?.color || "#666" }}
                    >
                      {entry.platform_name}
                    </span>
                  </td>
                  <td className="py-2 px-2 text-center font-medium">
                    {entry.best_rank != null ? `${entry.best_rank}위` : "-"}
                  </td>
                  <td className="py-2 px-2 text-center">
                    {entry.latest_rank != null ? (
                      <span>
                        {entry.latest_rank}위
                        {entry.latest_date && (
                          <span className="text-xs text-muted-foreground ml-1">
                            ({entry.latest_date.substring(5)})
                          </span>
                        )}
                      </span>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td className="py-2 px-2 text-center">
                    {entry.rating != null ? entry.rating.toFixed(1) : "-"}
                  </td>
                  <td className="py-2 px-2 text-center">
                    {entry.review_count != null ? entry.review_count.toLocaleString() : "-"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
