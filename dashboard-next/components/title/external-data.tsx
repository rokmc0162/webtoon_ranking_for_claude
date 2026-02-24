"use client";

import { useEffect, useState } from "react";
import type { ExternalDataResponse } from "@/lib/types";

interface ExternalDataProps {
  title: string;
  platformColor: string;
}

function formatNumber(n: number | null): string {
  if (n === null || n === undefined) return "-";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

export function ExternalData({ title, platformColor }: ExternalDataProps) {
  const [data, setData] = useState<ExternalDataResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/title-external?title=${encodeURIComponent(title)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [title]);

  if (loading) {
    return (
      <div className="bg-card rounded-xl border p-6 text-center">
        <div className="animate-pulse text-sm text-muted-foreground">
          외부 데이터 로딩 중...
        </div>
      </div>
    );
  }

  const hasAny =
    data?.anilist || data?.mal || data?.youtube ||
    data?.google_trends || data?.reddit || data?.bookwalker ||
    data?.pixiv || data?.amazon_jp || data?.twitter;

  if (!hasAny) {
    return (
      <div className="bg-card rounded-xl border border-dashed p-6 text-center text-muted-foreground">
        <p className="text-sm">🌐 외부 데이터</p>
        <p className="text-xs mt-1">수집된 외부 데이터가 없습니다</p>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-xl border p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-bold">🌐 외부 평가 데이터</h2>
        {data?.collected_date && (
          <span className="text-xs text-muted-foreground">
            수집: {data.collected_date}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {/* AniList */}
        {data?.anilist && (
          <div className="bg-muted rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold text-white bg-blue-500 px-2 py-0.5 rounded-full">
                AniList
              </span>
              {data.anilist.status && (
                <span className="text-xs text-muted-foreground">
                  {data.anilist.status}
                </span>
              )}
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-xs text-muted-foreground">점수</div>
                <div className="text-lg font-bold" style={{ color: platformColor }}>
                  {data.anilist.score ?? "-"}
                </div>
                <div className="text-xs text-muted-foreground">/100</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">인기도</div>
                <div className="text-lg font-bold">
                  {formatNumber(data.anilist.popularity)}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">팬 수</div>
                <div className="text-lg font-bold">
                  {formatNumber(data.anilist.members)}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* MAL */}
        {data?.mal && (
          <div className="bg-muted rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold text-white bg-[#2E51A2] px-2 py-0.5 rounded-full">
                MyAnimeList
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-xs text-muted-foreground">점수</div>
                <div className="text-lg font-bold" style={{ color: platformColor }}>
                  {data.mal.score?.toFixed(1) ?? "-"}
                </div>
                <div className="text-xs text-muted-foreground">/10</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">회원 수</div>
                <div className="text-lg font-bold">
                  {formatNumber(data.mal.members)}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">MAL 랭킹</div>
                <div className="text-lg font-bold">
                  {data.mal.rank ? `#${Math.round(data.mal.rank)}` : "-"}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* BookWalker */}
        {data?.bookwalker && (
          <div className="bg-muted rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold text-white bg-[#FF6600] px-2 py-0.5 rounded-full">
                BookWalker
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-xs text-muted-foreground">순위</div>
                <div className="text-lg font-bold" style={{ color: platformColor }}>
                  {data.bookwalker.bw_rank ? `#${Math.round(data.bookwalker.bw_rank)}` : "-"}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">평점</div>
                <div className="text-lg font-bold">
                  {data.bookwalker.bw_rating?.toFixed(1) ?? "-"}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">리뷰 수</div>
                <div className="text-lg font-bold">
                  {formatNumber(data.bookwalker.bw_review_count)}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Amazon JP */}
        {data?.amazon_jp && (
          <div className="bg-muted rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold text-white bg-[#FF9900] px-2 py-0.5 rounded-full">
                Amazon JP
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-xs text-muted-foreground">베스트셀러</div>
                <div className="text-lg font-bold" style={{ color: platformColor }}>
                  {data.amazon_jp.amazon_rank ? `#${Math.round(data.amazon_jp.amazon_rank)}` : "-"}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">평점</div>
                <div className="text-lg font-bold">
                  {data.amazon_jp.amazon_rating?.toFixed(1) ?? "-"}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">리뷰 수</div>
                <div className="text-lg font-bold">
                  {formatNumber(data.amazon_jp.amazon_review_count)}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Google Trends */}
        {data?.google_trends && (
          <div className="bg-muted rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold text-white bg-[#4285F4] px-2 py-0.5 rounded-full">
                Google Trends
              </span>
              <span className="text-xs text-muted-foreground">JP</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-center">
              <div>
                <div className="text-xs text-muted-foreground">최근 관심도</div>
                <div className="text-lg font-bold" style={{ color: platformColor }}>
                  {data.google_trends.interest_score ?? "-"}
                </div>
                <div className="text-xs text-muted-foreground">/100</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">3개월 평균</div>
                <div className="text-lg font-bold">
                  {data.google_trends.interest_avg_3m ?? "-"}
                </div>
                <div className="text-xs text-muted-foreground">/100</div>
              </div>
            </div>
          </div>
        )}

        {/* Reddit */}
        {data?.reddit && (
          <div className="bg-muted rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold text-white bg-[#FF4500] px-2 py-0.5 rounded-full">
                Reddit
              </span>
              <span className="text-xs text-muted-foreground">r/manga</span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-xs text-muted-foreground">토론 수</div>
                <div className="text-lg font-bold" style={{ color: platformColor }}>
                  {data.reddit.post_count ?? "-"}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">업보트</div>
                <div className="text-lg font-bold">
                  {formatNumber(data.reddit.total_score)}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">댓글 수</div>
                <div className="text-lg font-bold">
                  {formatNumber(data.reddit.total_comments)}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* YouTube */}
        {data?.youtube && (
          <div className="bg-muted rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold text-white bg-red-600 px-2 py-0.5 rounded-full">
                YouTube
              </span>
              {data.youtube.pv_count != null && (
                <span className="text-xs text-muted-foreground">
                  PV {data.youtube.pv_count}개
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 text-center">
              <div>
                <div className="text-xs text-muted-foreground">PV 최다 조회</div>
                <div className="text-lg font-bold" style={{ color: platformColor }}>
                  {formatNumber(data.youtube.pv_views)}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">총 조회수</div>
                <div className="text-lg font-bold">
                  {formatNumber(data.youtube.total_views)}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Pixiv */}
        {data?.pixiv && (
          <div className="bg-muted rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold text-white bg-[#0096FA] px-2 py-0.5 rounded-full">
                Pixiv
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-xs text-muted-foreground">팬아트</div>
                <div className="text-lg font-bold" style={{ color: platformColor }}>
                  {data.pixiv.fanart_count ?? "-"}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">북마크</div>
                <div className="text-lg font-bold">
                  {formatNumber(data.pixiv.fanart_bookmarks)}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">조회수</div>
                <div className="text-lg font-bold">
                  {formatNumber(data.pixiv.fanart_views)}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Twitter/X */}
        {data?.twitter && (
          <div className="bg-muted rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold text-white bg-black px-2 py-0.5 rounded-full">
                X (Twitter)
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-xs text-muted-foreground">트윗 수</div>
                <div className="text-lg font-bold" style={{ color: platformColor }}>
                  {data.twitter.tweet_count ?? "-"}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">좋아요</div>
                <div className="text-lg font-bold">
                  {formatNumber(data.twitter.total_likes)}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">리트윗</div>
                <div className="text-lg font-bold">
                  {formatNumber(data.twitter.total_retweets)}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
