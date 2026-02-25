import { sql } from "@/lib/supabase";
import { PLATFORMS } from "@/lib/constants";
import { UnifiedWorkClient } from "@/components/work/unified-work-client";
import type { Metadata } from "next";

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

  // 서버에서 직접 데이터 조회
  const metaRows = await sql`
    SELECT id, title_kr, title_en, title_canonical, author, artist, publisher,
           genre, genre_kr, tags, description, is_riverse,
           thumbnail_url, thumbnail_base64
    FROM unified_works
    WHERE id = ${numId}
    LIMIT 1
  `;

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

  // 플랫폼별 works
  const worksRows = await sql`
    SELECT platform, title, url, best_rank, rating, review_count,
           hearts, favorites, first_seen_date, last_seen_date
    FROM works
    WHERE unified_work_id = ${numId}
    ORDER BY platform
  `;

  // 각 플랫폼별 랭킹 데이터 병렬 조회
  const platforms = await Promise.all(
    worksRows.map(async (w) => {
      const pInfo = PLATFORMS.find((p) => p.id === w.platform);

      // 플랫폼의 첫 번째 장르 키가 "종합/overall" 역할
      // 대부분 플랫폼은 '' (빈문자열), Asura는 'all'
      const overallKey = pInfo?.genres[0]?.key ?? "";

      // 종합이 아닌 하위 장르 중 가장 많이 기록된 것 찾기
      const genreRows = overallKey === ""
        ? await sql`
            SELECT sub_category, COUNT(*)::int as cnt
            FROM rankings
            WHERE title = ${w.title} AND platform = ${w.platform}
              AND sub_category IS NOT NULL AND sub_category != ''
            GROUP BY sub_category
            ORDER BY cnt DESC
            LIMIT 1
          `
        : await sql`
            SELECT sub_category, COUNT(*)::int as cnt
            FROM rankings
            WHERE title = ${w.title} AND platform = ${w.platform}
              AND sub_category IS NOT NULL AND sub_category != ''
              AND sub_category != ${overallKey}
            GROUP BY sub_category
            ORDER BY cnt DESC
            LIMIT 1
          `;
      const genreKey = genreRows.length > 0 ? genreRows[0].sub_category : "";
      const genreLabel = genreKey
        ? (pInfo?.genres.find((g) => g.key === genreKey)?.label || genreKey)
        : "";

      // overallKey에 따라 종합 랭킹 쿼리 분기
      const [overallRows, genreRankRows, latestRows] = await Promise.all([
        overallKey === ""
          ? sql`
              SELECT date, rank::int as rank
              FROM rankings
              WHERE title = ${w.title} AND platform = ${w.platform}
                AND COALESCE(sub_category, '') = ''
              ORDER BY date DESC
              LIMIT 90
            `
          : sql`
              SELECT date, rank::int as rank
              FROM rankings
              WHERE title = ${w.title} AND platform = ${w.platform}
                AND sub_category = ${overallKey}
              ORDER BY date DESC
              LIMIT 90
            `,
        genreKey
          ? sql`
              SELECT date, rank::int as rank
              FROM rankings
              WHERE title = ${w.title} AND platform = ${w.platform}
                AND sub_category = ${genreKey}
              ORDER BY date DESC
              LIMIT 90
            `
          : Promise.resolve([]),
        overallKey === ""
          ? sql`
              SELECT rank::int as rank, date
              FROM rankings
              WHERE title = ${w.title} AND platform = ${w.platform}
                AND COALESCE(sub_category, '') = ''
              ORDER BY date DESC
              LIMIT 1
            `
          : sql`
              SELECT rank::int as rank, date
              FROM rankings
              WHERE title = ${w.title} AND platform = ${w.platform}
                AND sub_category = ${overallKey}
              ORDER BY date DESC
              LIMIT 1
            `,
      ]);

      return {
        platform: w.platform,
        platform_name: pInfo?.name || w.platform,
        platform_color: pInfo?.color || "#666",
        title: w.title,
        url: w.url || "",
        best_rank: w.best_rank ?? null,
        latest_rank: latestRows.length > 0 ? latestRows[0].rank : null,
        latest_date: latestRows.length > 0 ? String(latestRows[0].date) : null,
        rating: w.rating ? Number(w.rating) : null,
        review_count: w.review_count ?? null,
        hearts: w.hearts ?? null,
        favorites: w.favorites ?? null,
        first_seen_date: w.first_seen_date ? String(w.first_seen_date) : null,
        last_seen_date: w.last_seen_date ? String(w.last_seen_date) : null,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        rank_history: overallRows.map((r: any) => ({
          date: String(r.date),
          rank: r.rank as number,
        })),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        genre_rank_history: genreRankRows.map((r: any) => ({
          date: String(r.date),
          rank: r.rank as number,
        })),
        genre_label: genreLabel,
      };
    })
  );

  // 리뷰 통합
  const reviewRows = worksRows.length > 0
    ? await sql`
        SELECT r.platform, r.work_title, r.reviewer_name, r.reviewer_info,
               r.body, r.rating, r.likes_count, r.is_spoiler, r.reviewed_at
        FROM reviews r
        INNER JOIN works w ON w.platform = r.platform AND w.title = r.work_title
        WHERE w.unified_work_id = ${numId}
        ORDER BY r.reviewed_at DESC NULLS LAST, r.collected_at DESC
        LIMIT 50
      `
    : [];

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

  const ratingsWithValues = reviews
    .map((r) => r.rating)
    .filter((r): r is number => r !== null);
  const ratingDistribution: Record<number, number> = {};
  for (const r of ratingsWithValues) {
    ratingDistribution[r] = (ratingDistribution[r] || 0) + 1;
  }
  const avgRating =
    ratingsWithValues.length > 0
      ? ratingsWithValues.reduce((a, b) => a + b, 0) / ratingsWithValues.length
      : null;

  return (
    <UnifiedWorkClient
      data={{
        metadata,
        platforms,
        reviewStats: {
          total: reviews.length,
          avg_rating: avgRating ? Math.round(avgRating * 10) / 10 : null,
          rating_distribution: ratingDistribution,
        },
        reviews,
      }}
    />
  );
}
