"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import type { ReviewResponse, Review } from "@/lib/types";

function parseTags(raw: string): string[] {
  // JSON 배열 형식 ["tag1","tag2"] 또는 콤마 구분 "tag1,tag2" 모두 대응
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return [...new Set(parsed.map((t: string) => t.trim()).filter(Boolean))];
    }
  } catch {
    // JSON이 아니면 콤마 구분으로 처리
  }
  return [
    ...new Set(raw.split(",").map((t) => t.trim()).filter(Boolean)),
  ];
}

interface ReviewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  titleKr: string;
  platform: string;
  platformColor: string;
}

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
  const isLong = review.body.length > 150;

  return (
    <div className="py-3 first:pt-0">
      {/* 헤더: 작성자 + 날짜 + 별점 */}
      <div className="flex items-center gap-2 mb-1 flex-wrap">
        <span className="text-sm font-medium text-foreground">
          {review.reviewer_name || "익명"}
        </span>
        {review.reviewer_info && (
          <span className="text-xs text-muted-foreground">
            ({review.reviewer_info})
          </span>
        )}
        {review.rating != null && <StarRating rating={review.rating} />}
        {review.reviewed_at && (
          <span className="text-xs text-muted-foreground ml-auto">
            {review.reviewed_at}
          </span>
        )}
      </div>

      {/* 본문 */}
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
                {review.body.slice(0, 150)}...
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

      {/* 좋아요 */}
      {review.likes_count > 0 && (
        <div className="mt-1 text-xs text-muted-foreground">
          👍 {review.likes_count}
        </div>
      )}
    </div>
  );
}

const REVIEWS_PER_PAGE = 30;

export function ReviewDialog({
  open,
  onOpenChange,
  title,
  titleKr,
  platform,
  platformColor,
}: ReviewDialogProps) {
  const [data, setData] = useState<ReviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [visibleCount, setVisibleCount] = useState(REVIEWS_PER_PAGE);

  useEffect(() => {
    if (!open || !title) return;
    setLoading(true);
    setData(null);
    setVisibleCount(REVIEWS_PER_PAGE);
    fetch(
      `/api/reviews?platform=${encodeURIComponent(platform)}&title=${encodeURIComponent(title)}`
    )
      .then((res) => res.json())
      .then((d: ReviewResponse) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [open, title, platform]);

  const meta = data?.metadata;
  const reviews = data?.reviews || [];
  const isPiccoma = platform === "piccoma";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[680px] max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-lg flex items-center gap-2">
            <span style={{ color: platformColor }}>💬</span> {title}
          </DialogTitle>
          {titleKr && <DialogDescription>{titleKr}</DialogDescription>}
        </DialogHeader>

        {loading ? (
          <div className="h-[200px] flex items-center justify-center text-muted-foreground">
            로딩 중...
          </div>
        ) : !data ? (
          <div className="h-[200px] flex items-center justify-center text-muted-foreground">
            데이터를 불러올 수 없습니다.
          </div>
        ) : (
          <div className="flex flex-col gap-4 overflow-y-auto min-h-0">
            {/* 메타데이터 카드 */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-sm">
              {meta?.author && (
                <div className="bg-muted rounded-lg p-2.5">
                  <div className="text-xs text-muted-foreground mb-0.5">
                    작가
                  </div>
                  <div className="font-medium text-foreground truncate">
                    {meta.author}
                  </div>
                </div>
              )}
              {meta?.publisher && (
                <div className="bg-muted rounded-lg p-2.5">
                  <div className="text-xs text-muted-foreground mb-0.5">
                    출판사
                  </div>
                  <div className="font-medium text-foreground truncate">
                    {meta.publisher}
                  </div>
                </div>
              )}
              {meta?.label && (
                <div className="bg-muted rounded-lg p-2.5">
                  <div className="text-xs text-muted-foreground mb-0.5">
                    레이블
                  </div>
                  <div className="font-medium text-foreground truncate">
                    {meta.label}
                  </div>
                </div>
              )}

              {/* 픽코마: 하트수 */}
              {isPiccoma && meta?.hearts != null && (
                <div className="bg-muted rounded-lg p-2.5">
                  <div className="text-xs text-muted-foreground mb-0.5">
                    하트
                  </div>
                  <div className="font-medium text-foreground">
                    ❤️ {meta.hearts.toLocaleString()}
                  </div>
                </div>
              )}

              {/* 나머지 플랫폼: 평점 + 리뷰수 */}
              {!isPiccoma && meta?.rating != null && (
                <div className="bg-muted rounded-lg p-2.5">
                  <div className="text-xs text-muted-foreground mb-0.5">
                    평점
                  </div>
                  <div className="font-medium text-foreground flex items-center gap-1">
                    <StarRating rating={Math.round(meta.rating)} />
                    <span className="text-xs text-muted-foreground">
                      ({meta.rating.toFixed(1)})
                    </span>
                  </div>
                </div>
              )}
              {!isPiccoma && meta?.review_count != null && (
                <div className="bg-muted rounded-lg p-2.5">
                  <div className="text-xs text-muted-foreground mb-0.5">
                    리뷰 수
                  </div>
                  <div className="font-medium text-foreground">
                    {meta.review_count.toLocaleString()}건
                  </div>
                </div>
              )}

              {/* 라인망가: 즐겨찾기 */}
              {platform === "linemanga" && meta?.favorites != null && (
                <div className="bg-muted rounded-lg p-2.5">
                  <div className="text-xs text-muted-foreground mb-0.5">
                    즐겨찾기
                  </div>
                  <div className="font-medium text-foreground">
                    ⭐ {meta.favorites.toLocaleString()}
                  </div>
                </div>
              )}
            </div>

            {/* 태그 */}
            {meta?.tags && (
              <div className="flex flex-wrap gap-1.5">
                {parseTags(meta.tags).map((tag) => (
                  <span
                    key={tag}
                    className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded-full"
                  >
                    #{tag}
                  </span>
                ))}
              </div>
            )}

            {/* 리뷰 리스트 */}
            {isPiccoma ? (
              <div className="text-sm text-muted-foreground text-center py-6">
                픽코마는 리뷰/코멘트 기능이 없습니다.
                <br />
                하트수로 인기도를 확인해주세요.
              </div>
            ) : reviews.length > 0 ? (
              <>
                <Separator />
                <div className="text-sm font-medium text-foreground">
                  리뷰/코멘트 ({reviews.length}건)
                </div>
                <div className="divide-y divide-border">
                  {reviews.slice(0, visibleCount).map((r, i) => (
                    <ReviewCard key={i} review={r} />
                  ))}
                </div>
                {visibleCount < reviews.length && (
                  <button
                    onClick={() => setVisibleCount((v) => v + REVIEWS_PER_PAGE)}
                    className="w-full py-2 text-sm text-blue-500 hover:text-blue-600 hover:bg-muted/50 rounded-lg transition-colors cursor-pointer"
                  >
                    더보기 ({reviews.length - visibleCount}건 남음)
                  </button>
                )}
              </>
            ) : (
              <>
                <Separator />
                <div className="text-sm text-muted-foreground text-center py-6">
                  수집된 리뷰가 없습니다.
                  <br />
                  주간 리뷰 수집 후 확인할 수 있습니다.
                </div>
              </>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
