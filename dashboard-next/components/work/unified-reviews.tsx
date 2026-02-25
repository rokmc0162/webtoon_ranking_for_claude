"use client";

import { useState } from "react";
import { getPlatformById } from "@/lib/constants";
import type { ReviewStats, ReviewWithPlatform } from "@/lib/types";

interface UnifiedReviewsProps {
  reviews: ReviewWithPlatform[];
  reviewStats: ReviewStats;
}

export function UnifiedReviews({ reviews, reviewStats }: UnifiedReviewsProps) {
  const [showAll, setShowAll] = useState(false);

  if (reviews.length === 0) return null;

  const visible = showAll ? reviews : reviews.slice(0, 10);

  return (
    <div className="bg-card rounded-xl border p-4 sm:p-6">
      <h2 className="text-base font-bold mb-4">💬 통합 리뷰 ({reviewStats.total}건)</h2>

      {/* 평점 통계 */}
      {reviewStats.avg_rating != null && (
        <div className="mb-4 p-3 bg-muted rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-yellow-500 text-sm">
              {"★".repeat(Math.round(reviewStats.avg_rating))}
              {"☆".repeat(5 - Math.round(reviewStats.avg_rating))}
            </span>
            <span className="text-sm text-muted-foreground">
              {reviewStats.avg_rating}점 ({reviewStats.total}건)
            </span>
          </div>
          <div className="space-y-1">
            {[5, 4, 3, 2, 1].map((star) => {
              const count = reviewStats.rating_distribution[star] || 0;
              const pct = reviewStats.total > 0 ? (count / reviewStats.total) * 100 : 0;
              return (
                <div key={star} className="flex items-center gap-2 text-xs">
                  <span className="w-8 text-right text-muted-foreground">{star}점</span>
                  <div className="flex-1 h-2 bg-background rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-yellow-500 transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="w-8 text-muted-foreground">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 리뷰 목록 */}
      <div className="space-y-3">
        {visible.map((r, i) => {
          const pInfo = getPlatformById(r.platform);
          return (
            <div key={i} className="border rounded-lg p-3">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{r.reviewer_name || "익명"}</span>
                  {r.platform && (
                    <span
                      className="text-[10px] px-1.5 py-0.5 rounded-full text-white"
                      style={{ backgroundColor: pInfo?.color || "#666" }}
                    >
                      {pInfo?.name || r.platform}
                    </span>
                  )}
                  {r.rating != null && (
                    <span className="text-yellow-500 text-xs">
                      {"★".repeat(r.rating)}{"☆".repeat(5 - r.rating)}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  {r.likes_count > 0 && <span>👍 {r.likes_count}</span>}
                  {r.reviewed_at && <span>{r.reviewed_at}</span>}
                </div>
              </div>
              {r.is_spoiler ? (
                <SpoilerText body={r.body} />
              ) : (
                <p className="text-sm text-foreground/80 leading-relaxed line-clamp-3">
                  {r.body}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {reviews.length > 10 && !showAll && (
        <button
          onClick={() => setShowAll(true)}
          className="mt-3 w-full py-2 text-sm text-blue-500 hover:underline cursor-pointer"
        >
          전체 {reviews.length}건 보기
        </button>
      )}
    </div>
  );
}

function SpoilerText({ body }: { body: string }) {
  const [revealed, setRevealed] = useState(false);
  return revealed ? (
    <p className="text-sm text-foreground/80 leading-relaxed line-clamp-3">{body}</p>
  ) : (
    <button
      onClick={() => setRevealed(true)}
      className="text-sm text-muted-foreground bg-muted px-3 py-1.5 rounded cursor-pointer"
    >
      ⚠️ 스포일러 포함 - 클릭하여 보기
    </button>
  );
}
