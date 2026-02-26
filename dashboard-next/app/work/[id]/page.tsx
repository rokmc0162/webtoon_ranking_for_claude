import { sql } from "@/lib/supabase";
import { PLATFORMS } from "@/lib/constants";
import { UnifiedWorkClient } from "@/components/work/unified-work-client";
import type { Metadata } from "next";

// 빌드 시 DB 연결 불가 → 런타임 렌더링 필수
export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const rows = await sql`
    SELECT title_kr, title_canonical FROM unified_works WHERE id = ${parseInt(id, 10)} LIMIT 1
  `;
  const title = rows.length > 0
    ? `${rows[0].title_kr || rows[0].title_canonical} - 통합 작품 분석`
    : "작품 분석";
  return { title };
}

export default async function UnifiedWorkPage({ params }: Props) {
  const { id } = await params;
  const numId = parseInt(id, 10);

  if (isNaN(numId)) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">잘못된 작품 ID입니다.</p>
      </div>
    );
  }

  // 메타데이터 + 플랫폼별 works를 병렬 조회
  const [metaRows, worksRows] = await Promise.all([
    sql`
      SELECT id, title_kr, title_en, title_canonical, author, artist, publisher,
             genre, genre_kr, tags, description, is_riverse,
             thumbnail_url, thumbnail_base64
      FROM unified_works
      WHERE id = ${numId}
      LIMIT 1
    `,
    sql`
      SELECT platform, title, url, best_rank, rating, review_count,
             hearts, favorites, first_seen_date, last_seen_date
      FROM works
      WHERE unified_work_id = ${numId}
      ORDER BY platform
    `,
  ]);

  if (metaRows.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">작품을 찾을 수 없습니다.</p>
      </div>
    );
  }

  const uw = metaRows[0];
  const metadata = {
    id: uw.id,
    title_kr: uw.title_kr || "",
    title_en: uw.title_en || "",
    title_canonical: uw.title_canonical || "",
    author: uw.author || "",
    artist: uw.artist || "",
    publisher: uw.publisher || "",
    genre: uw.genre || "",
    genre_kr: uw.genre_kr || "",
    tags: uw.tags || "",
    description: uw.description || "",
    is_riverse: uw.is_riverse ?? false,
    thumbnail_url: uw.thumbnail_url || null,
    thumbnail_base64: uw.thumbnail_base64 || null,
  };

  // 모든 플랫폼의 장르 + 랭킹 히스토리를 한 번에 조회 (개별 쿼리 대신 벌크)
  const allTitles = worksRows.map((w) => w.title);
  const allPlatforms = worksRows.map((w) => w.platform);

  // 장르 분류 + 종합 랭킹 + 최신 순위를 벌크 쿼리로 한 번에 (병렬 3개)
  const [genreBulk, rankBulk, reviewBulk] = await Promise.all([
    // 1. 모든 작품의 장르별 카운트 (상위 1개만 필요하지만 모두 가져와서 JS에서 처리)
    sql`
      SELECT title, platform, sub_category, COUNT(*)::int as cnt
      FROM rankings
      WHERE title = ANY(${allTitles}) AND platform = ANY(${allPlatforms})
        AND sub_category IS NOT NULL AND sub_category != ''
      GROUP BY title, platform, sub_category
      ORDER BY title, platform, cnt DESC
    `,
    // 2. 모든 작품의 랭킹 히스토리 (최근 90일)
    sql`
      SELECT title, platform, sub_category, date, rank::int as rank
      FROM rankings
      WHERE title = ANY(${allTitles}) AND platform = ANY(${allPlatforms})
      ORDER BY title, platform, date DESC
    `,
    // 3. 리뷰 (초기 50건 + 전체 수 + 평점 분포 — 병렬)
    worksRows.length > 0
      ? Promise.all([
          sql`
            SELECT r.platform, r.work_title, r.reviewer_name, r.reviewer_info,
                   r.body, r.rating, r.likes_count, r.is_spoiler, r.reviewed_at
            FROM reviews r
            INNER JOIN works w ON w.platform = r.platform AND w.title = r.work_title
            WHERE w.unified_work_id = ${numId}
            ORDER BY r.reviewed_at DESC NULLS LAST, r.collected_at DESC
            LIMIT 50
          `,
          sql`
            SELECT COUNT(*)::int as total
            FROM reviews r
            INNER JOIN works w ON w.platform = r.platform AND w.title = r.work_title
            WHERE w.unified_work_id = ${numId}
          `,
          sql`
            SELECT r.rating, COUNT(*)::int as cnt
            FROM reviews r
            INNER JOIN works w ON w.platform = r.platform AND w.title = r.work_title
            WHERE w.unified_work_id = ${numId} AND r.rating IS NOT NULL
            GROUP BY r.rating
            ORDER BY r.rating
          `,
        ])
      : Promise.resolve([[], [{ total: 0 }], []]),
  ]);

  const [reviewRows, reviewCountRows, ratingDistRows] = reviewBulk as [
    typeof worksRows, Array<{ total: number }>, Array<{ rating: number; cnt: number }>
  ];

  // 장르 벌크 데이터를 플랫폼별로 정리
  const genreMap = new Map<string, string>(); // "platform:title" → top genre key
  for (const row of genreBulk) {
    const key = `${row.platform}:${row.title}`;
    if (!genreMap.has(key)) {
      // 첫 번째 = cnt DESC 최상위
      const pInfo = PLATFORMS.find((p) => p.id === row.platform);
      const overallKey = pInfo?.genres[0]?.key ?? "";
      // overall 키는 제외하고 장르 찾기
      if (row.sub_category !== overallKey) {
        genreMap.set(key, row.sub_category);
      }
    }
  }

  // 랭킹 벌크 데이터를 플랫폼별로 분류
  type RankEntry = { date: string; rank: number };
  const rankMap = new Map<string, { overall: RankEntry[]; genre: RankEntry[]; latest: RankEntry | null }>();

  for (const w of worksRows) {
    const pInfo = PLATFORMS.find((p) => p.id === w.platform);
    const overallKey = pInfo?.genres[0]?.key ?? "";
    const genreKey = genreMap.get(`${w.platform}:${w.title}`) || "";
    const mapKey = `${w.platform}:${w.title}`;

    const overall: RankEntry[] = [];
    const genre: RankEntry[] = [];
    let latest: RankEntry | null = null;

    for (const r of rankBulk) {
      if (r.title !== w.title || r.platform !== w.platform) continue;
      const sc = r.sub_category || "";
      const entry = { date: String(r.date), rank: r.rank };

      // 종합 랭킹
      if (overallKey === "" ? sc === "" : sc === overallKey) {
        if (overall.length < 90) overall.push(entry);
        if (!latest) latest = entry;
      }
      // 장르 랭킹
      if (genreKey && sc === genreKey && genre.length < 90) {
        genre.push(entry);
      }
    }

    rankMap.set(mapKey, { overall, genre, latest });
  }

  // 플랫폼 데이터 조립
  const platforms = worksRows.map((w) => {
    const pInfo = PLATFORMS.find((p) => p.id === w.platform);
    const mapKey = `${w.platform}:${w.title}`;
    const genreKey = genreMap.get(mapKey) || "";
    const genreLabel = genreKey
      ? (pInfo?.genres.find((g) => g.key === genreKey)?.label || genreKey)
      : "";
    const ranks = rankMap.get(mapKey) || { overall: [], genre: [], latest: null };

    return {
      platform: w.platform,
      platform_name: pInfo?.name || w.platform,
      platform_color: pInfo?.color || "#666",
      title: w.title,
      url: w.url || "",
      best_rank: w.best_rank ?? null,
      latest_rank: ranks.latest ? ranks.latest.rank : null,
      latest_date: ranks.latest ? ranks.latest.date : null,
      rating: w.rating ? Number(w.rating) : null,
      review_count: w.review_count ?? null,
      hearts: w.hearts ?? null,
      favorites: w.favorites ?? null,
      first_seen_date: w.first_seen_date ? String(w.first_seen_date) : null,
      last_seen_date: w.last_seen_date ? String(w.last_seen_date) : null,
      rank_history: ranks.overall,
      genre_rank_history: ranks.genre,
      genre_label: genreLabel,
    };
  });

  // 리뷰 처리
  const reviews = reviewRows.map((r) => ({
    reviewer_name: r.reviewer_name || "",
    reviewer_info: r.reviewer_info || "",
    body: r.body || "",
    rating: r.rating ?? null,
    likes_count: r.likes_count ?? 0,
    is_spoiler: r.is_spoiler ?? false,
    reviewed_at: r.reviewed_at
      ? new Date(r.reviewed_at).toISOString().split("T")[0]
      : null,
    platform: r.platform || "",
  }));

  const totalReviews = reviewCountRows[0]?.total || 0;

  // 전체 평점분포
  const ratingDistribution: Record<number, number> = {};
  let totalRated = 0;
  let ratingSum = 0;
  for (const row of ratingDistRows) {
    if (row.rating != null) {
      const r = Number(row.rating);
      const cnt = Number(row.cnt);
      ratingDistribution[r] = cnt;
      totalRated += cnt;
      ratingSum += r * cnt;
    }
  }
  const avgRating = totalRated > 0 ? ratingSum / totalRated : null;

  return (
    <UnifiedWorkClient
      data={{
        metadata,
        platforms,
        reviewStats: {
          total: totalReviews,
          avg_rating: avgRating ? Math.round(avgRating * 10) / 10 : null,
          rating_distribution: ratingDistribution,
        },
        reviews,
      }}
    />
  );
}
