"use client";

import type { TitleDetailMetadata, ReviewStats } from "@/lib/types";

interface PlatformMetricsProps {
  metadata: TitleDetailMetadata;
  reviewStats: ReviewStats;
  platformColor: string;
}

function StarRating({ rating }: { rating: number }) {
  const full = Math.round(rating);
  return (
    <span className="text-yellow-500 text-sm tracking-tight">
      {"★".repeat(full)}
      {"☆".repeat(5 - full)}
    </span>
  );
}

export function PlatformMetrics({ metadata, reviewStats, platformColor }: PlatformMetricsProps) {
  const isPiccoma = metadata.platform === "piccoma";

  const cards: { label: string; value: string; icon: string }[] = [];

  if (isPiccoma && metadata.hearts != null) {
    cards.push({ label: "하트", value: metadata.hearts.toLocaleString(), icon: "❤️" });
  }
  if (!isPiccoma && metadata.rating != null) {
    cards.push({ label: "평점", value: metadata.rating.toFixed(1), icon: "⭐" });
  }
  if (!isPiccoma && metadata.review_count != null) {
    cards.push({ label: "리뷰 수", value: `${metadata.review_count.toLocaleString()}건`, icon: "💬" });
  }
  if (metadata.platform === "linemanga" && metadata.favorites != null) {
    cards.push({ label: "즐겨찾기", value: metadata.favorites.toLocaleString(), icon: "⭐" });
  }
  if (reviewStats.total > 0) {
    cards.push({ label: "수집 리뷰", value: `${reviewStats.total}건`, icon: "📝" });
  }
  if (reviewStats.avg_rating != null) {
    cards.push({ label: "평균 평점", value: `${reviewStats.avg_rating}점`, icon: "📊" });
  }

  if (cards.length === 0) return null;

  return (
    <div className="bg-card rounded-xl border p-4 sm:p-6">
      <h2 className="text-base font-bold mb-4">📈 플랫폼 지표</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {cards.map((card) => (
          <div key={card.label} className="bg-muted rounded-lg p-3 text-center">
            <div className="text-xs text-muted-foreground mb-1">{card.icon} {card.label}</div>
            <div className="text-lg font-bold" style={{ color: platformColor }}>
              {card.value}
            </div>
          </div>
        ))}
      </div>

      {/* 평점 분포 바 */}
      {reviewStats.avg_rating != null && Object.keys(reviewStats.rating_distribution).length > 0 && (
        <div className="mt-4">
          <div className="flex items-center gap-2 mb-2">
            <StarRating rating={Math.round(reviewStats.avg_rating)} />
            <span className="text-sm text-muted-foreground">
              {reviewStats.avg_rating}점 (리뷰 {reviewStats.total}건 기준)
            </span>
          </div>
          <div className="space-y-1">
            {[5, 4, 3, 2, 1].map((star) => {
              const count = reviewStats.rating_distribution[star] || 0;
              const pct = reviewStats.total > 0 ? (count / reviewStats.total) * 100 : 0;
              return (
                <div key={star} className="flex items-center gap-2 text-xs">
                  <span className="w-8 text-right text-muted-foreground">{star}점</span>
                  <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${pct}%`, backgroundColor: platformColor }}
                    />
                  </div>
                  <span className="w-8 text-muted-foreground">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
