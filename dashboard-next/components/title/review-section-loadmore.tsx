"use client";

import { useState, useMemo, useCallback } from "react";
import { Separator } from "@/components/ui/separator";
import type { Review } from "@/lib/types";

type SortMode = "newest" | "oldest" | "likes" | "rating_high" | "rating_low";

function StarRating({ rating }: { rating: number }) {
  return (
    <span className="text-yellow-500 text-sm tracking-tight">
      {"★".repeat(rating)}
      {"☆".repeat(5 - rating)}
    </span>
  );
}

function ReviewCard({ review }: { review: Review }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = review.body.length > 200;

  return (
    <div className="py-3 first:pt-0">
      <div className="flex items-center gap-2 mb-1 flex-wrap">
        <span className="text-sm font-medium text-foreground">
          {review.reviewer_name || "익명"}
        </span>
        {review.reviewer_info && (
          <span className="text-xs text-muted-foreground">({review.reviewer_info})</span>
        )}
        {review.rating != null && <StarRating rating={review.rating} />}
        {review.reviewed_at && (
          <span className="text-xs text-muted-foreground ml-auto">{review.reviewed_at}</span>
        )}
      </div>

      <div className="text-sm text-foreground/90 leading-relaxed">
        {review.is_spoiler && !expanded ? (
          <button
            onClick={() => setExpanded(true)}
            className="text-red-500 text-xs border border-red-200 rounded px-2 py-1 hover:bg-red-50 transition-colors cursor-pointer"
          >
            ネタバレ (스포일러) — 클릭하여 표시
          </button>
        ) : (
          <>
            {isLong && !expanded ? (
              <>
                {review.body.slice(0, 200)}...
                <button
                  onClick={() => setExpanded(true)}
                  className="ml-1 text-xs text-blue-500 hover:underline cursor-pointer"
                >
                  더보기
                </button>
              </>
            ) : (
              review.body
            )}
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

      {review.likes_count > 0 && (
        <div className="mt-1 text-xs text-muted-foreground">👍 {review.likes_count}</div>
      )}
    </div>
  );
}

const REVIEWS_PER_PAGE = 30;
const LOAD_MORE_BATCH = 50;

interface ReviewSectionWithLoadMoreProps {
  initialReviews: Review[];
  totalReviews: number;
  platform: string;
  title: string;
  platformColor: string;
}

export function ReviewSectionWithLoadMore({
  initialReviews,
  totalReviews,
  platform,
  title,
  platformColor,
}: ReviewSectionWithLoadMoreProps) {
  const [allReviews, setAllReviews] = useState<Review[]>(initialReviews);
  const [sortMode, setSortMode] = useState<SortMode>("newest");
  const [visibleCount, setVisibleCount] = useState(REVIEWS_PER_PAGE);
  const [loadingMore, setLoadingMore] = useState(false);
  const isPiccoma = platform === "piccoma";

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
        `/api/reviews?platform=${encodeURIComponent(platform)}&title=${encodeURIComponent(title)}&offset=${offset}&limit=${LOAD_MORE_BATCH}`
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
  }, [loadingMore, hasMoreOnServer, allReviews.length, platform, title]);

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
    { key: "rating_high", label: "평점 높은순" },
    { key: "rating_low", label: "평점 낮은순" },
  ];

  return (
    <div className="bg-card rounded-xl border p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-bold">💬 리뷰/코멘트</h2>
        {!isPiccoma && allReviews.length > 0 && (
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
                    ? "text-white font-medium"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
                style={sortMode === opt.key ? { backgroundColor: platformColor } : undefined}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {isPiccoma ? (
        <div className="text-sm text-muted-foreground text-center py-8">
          픽코마는 리뷰/코멘트 기능이 없습니다.
          <br />
          하트수로 인기도를 확인해주세요.
        </div>
      ) : sorted.length > 0 ? (
        <>
          <div className="text-xs text-muted-foreground mb-3">
            총 {totalReviews}건의 리뷰 (로드됨: {allReviews.length}건)
          </div>
          <Separator className="mb-3" />
          <div className="divide-y divide-border">
            {sorted.slice(0, visibleCount).map((r, i) => (
              <ReviewCard key={`${r.reviewer_name}-${r.reviewed_at}-${i}`} review={r} />
            ))}
          </div>

          {/* 더보기 버튼 */}
          {hasMoreToShow && (
            <button
              onClick={handleShowMore}
              disabled={loadingMore}
              className="w-full py-2 mt-3 text-sm text-blue-500 hover:text-blue-600 hover:bg-muted/50 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
            >
              {loadingMore ? (
                "로딩 중..."
              ) : (
                <>
                  더보기 ({totalReviews - Math.min(visibleCount, allReviews.length)}건 남음)
                </>
              )}
            </button>
          )}
        </>
      ) : (
        <div className="text-sm text-muted-foreground text-center py-8">
          수집된 리뷰가 없습니다.
          <br />
          주간 리뷰 수집 후 확인할 수 있습니다.
        </div>
      )}
    </div>
  );
}
