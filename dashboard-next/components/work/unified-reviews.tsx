"use client";

import { useState, useMemo, useCallback } from "react";
import { getPlatformById } from "@/lib/constants";
import type { ReviewStats, ReviewWithPlatform } from "@/lib/types";

type SortMode = "newest" | "oldest" | "likes" | "rating_high" | "rating_low";

const REVIEWS_PER_PAGE = 20;
const LOAD_MORE_BATCH = 50;

interface UnifiedReviewsProps {
  initialReviews: ReviewWithPlatform[];
  totalReviews: number;
  reviewStats: ReviewStats;
  workId: number;
}

export function UnifiedReviews({
  initialReviews,
  totalReviews,
  reviewStats,
  workId,
}: UnifiedReviewsProps) {
  const [allReviews, setAllReviews] = useState<ReviewWithPlatform[]>(initialReviews);
  const [sortMode, setSortMode] = useState<SortMode>("newest");
  const [visibleCount, setVisibleCount] = useState(REVIEWS_PER_PAGE);
  const [loadingMore, setLoadingMore] = useState(false);

  const hasMoreOnServer = allReviews.length < totalReviews;
  const hasMoreToShow = visibleCount < allReviews.length || hasMoreOnServer;

  const sorted = useMemo(() => {
    const copy = [...allReviews];
    switch (sortMode) {
      case "newest":
        return copy.sort((a, b) => (b.reviewed_at || "").localeCompare(a.reviewed_at || ""));
      case "oldest":
        return copy.sort((a, b) => (a.reviewed_at || "").localeCompare(b.reviewed_at || ""));
      case "likes":
        return copy.sort((a, b) => b.likes_count - a.likes_count);
      case "rating_high":
        return copy.sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0));
      case "rating_low":
        return copy.sort((a, b) => (a.rating ?? 6) - (b.rating ?? 6));
      default:
        return copy;
    }
  }, [allReviews, sortMode]);

  // 서버에서 추가 리뷰 로드
  const loadMoreFromServer = useCallback(async () => {
    if (loadingMore || !hasMoreOnServer) return;
    setLoadingMore(true);
    try {
      const offset = allReviews.length;
      const res = await fetch(
        `/api/work-reviews?work_id=${workId}&offset=${offset}&limit=${LOAD_MORE_BATCH}`
      );
      const data = await res.json();
      if (data.reviews && data.reviews.length > 0) {
        setAllReviews((prev) => [...prev, ...data.reviews]);
      }
    } catch (e) {
      console.error("Failed to load more reviews:", e);
    } finally {
      setLoadingMore(false);
    }
  }, [loadingMore, hasMoreOnServer, allReviews.length, workId]);

  const handleShowMore = () => {
    const nextVisible = visibleCount + REVIEWS_PER_PAGE;
    setVisibleCount(nextVisible);
    // 보여줄 수 있는 리뷰가 부족하면 서버에서 더 로드
    if (nextVisible >= allReviews.length && hasMoreOnServer) {
      loadMoreFromServer();
    }
  };

  const sortOptions: { key: SortMode; label: string }[] = [
    { key: "newest", label: "최신순" },
    { key: "oldest", label: "오래된순" },
    { key: "likes", label: "좋아요순" },
    { key: "rating_high", label: "평점높은순" },
    { key: "rating_low", label: "평점낮은순" },
  ];

  if (initialReviews.length === 0 && totalReviews === 0) return null;

  return (
    <div className="bg-card rounded-xl border p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h2 className="text-base font-bold">
          💬 통합 리뷰 ({totalReviews.toLocaleString()}건)
        </h2>
        {allReviews.length > 0 && (
          <div className="flex gap-1">
            {sortOptions.map((opt) => (
              <button
                key={opt.key}
                onClick={() => {
                  setSortMode(opt.key);
                  setVisibleCount(REVIEWS_PER_PAGE);
                }}
                className={`px-2 py-1 text-xs rounded-full transition-colors cursor-pointer ${
                  sortMode === opt.key
                    ? "bg-foreground text-background font-medium"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 평점 통계 */}
      {reviewStats.avg_rating != null && (
        <div className="mb-4 p-3 bg-muted rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-yellow-500 text-sm">
              {"★".repeat(Math.round(reviewStats.avg_rating))}
              {"☆".repeat(5 - Math.round(reviewStats.avg_rating))}
            </span>
            <span className="text-sm text-muted-foreground">
              {reviewStats.avg_rating}점 ({totalReviews.toLocaleString()}건)
            </span>
          </div>
          <div className="space-y-1">
            {[5, 4, 3, 2, 1].map((star) => {
              const count = reviewStats.rating_distribution[star] || 0;
              const pct = totalReviews > 0 ? (count / totalReviews) * 100 : 0;
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

      {allReviews.length > 0 ? (
        <>
          <div className="text-xs text-muted-foreground mb-3">
            총 {totalReviews.toLocaleString()}건의 리뷰 (로드됨: {allReviews.length.toLocaleString()}건)
          </div>

          {/* 리뷰 목록 */}
          <div className="space-y-3">
            {sorted.slice(0, visibleCount).map((r, i) => {
              const pInfo = getPlatformById(r.platform);
              return (
                <div key={`${r.platform}-${r.reviewer_name}-${r.reviewed_at}-${i}`} className="border rounded-lg p-3">
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
                    <ReviewBody body={r.body} />
                  )}
                </div>
              );
            })}
          </div>

          {/* 더보기 버튼 */}
          {hasMoreToShow && (
            <button
              onClick={handleShowMore}
              disabled={loadingMore}
              className="w-full py-2.5 mt-3 text-sm text-blue-500 hover:text-blue-600 hover:bg-muted/50 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
            >
              {loadingMore ? (
                "로딩 중..."
              ) : (
                <>더보기 ({(totalReviews - Math.min(visibleCount, allReviews.length)).toLocaleString()}건 남음)</>
              )}
            </button>
          )}
        </>
      ) : (
        <div className="text-sm text-muted-foreground text-center py-8">
          수집된 리뷰가 없습니다.
        </div>
      )}
    </div>
  );
}

function ReviewBody({ body }: { body: string }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = body.length > 200;

  return (
    <div className="text-sm text-foreground/80 leading-relaxed">
      {isLong && !expanded ? (
        <>
          {body.slice(0, 200)}...
          <button
            onClick={() => setExpanded(true)}
            className="ml-1 text-xs text-blue-500 hover:underline cursor-pointer"
          >
            더보기
          </button>
        </>
      ) : (
        <>
          {body}
          {isLong && expanded && (
            <button
              onClick={() => setExpanded(false)}
              className="ml-1 text-xs text-blue-500 hover:underline cursor-pointer"
            >
              접기
            </button>
          )}
        </>
      )}
    </div>
  );
}

function SpoilerText({ body }: { body: string }) {
  const [revealed, setRevealed] = useState(false);
  return revealed ? (
    <ReviewBody body={body} />
  ) : (
    <button
      onClick={() => setRevealed(true)}
      className="text-sm text-muted-foreground bg-muted px-3 py-1.5 rounded cursor-pointer"
    >
      ⚠️ 스포일러 포함 - 클릭하여 보기
    </button>
  );
}
