import { sql } from "@/lib/supabase";
import { PLATFORMS } from "@/lib/constants";
import { notFound } from "next/navigation";
import { TitleDetailClient } from "@/components/title/title-detail-client";

// 동적 렌더링 강제
export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ platform: string; encodedTitle: string }>;
}

// 서버 컴포넌트: API 호출 대신 직접 DB 조회 → cold start 워터폴 제거
export default async function TitleDetailPage({ params }: PageProps) {
  const { platform, encodedTitle } = await params;
  const title = decodeURIComponent(encodedTitle);

  // 1단계: 메타데이터 + 랭킹히스토리 + 장르 + 리뷰(초기 50건) + 전체 리뷰 수를 병렬 조회
  const [metaRows, overallRows, genreRows, reviewRows, reviewCountRows] = await Promise.all([
    sql`
      SELECT platform, title, title_kr, genre, genre_kr, is_riverse, url,
             thumbnail_url, thumbnail_base64,
             author, publisher, label, tags, description,
             hearts, favorites, rating, review_count,
             best_rank,
             first_seen_date::text as first_seen_date,
             last_seen_date::text as last_seen_date
      FROM works
      WHERE platform = ${platform} AND title = ${title}
      LIMIT 1
    `,
    sql`
      SELECT date::text as date, rank::int as rank
      FROM rankings
      WHERE title = ${title} AND platform = ${platform}
        AND COALESCE(sub_category, '') = ''
      ORDER BY date DESC
      LIMIT 90
    `,
    sql`
      SELECT sub_category, COUNT(*)::int as cnt
      FROM rankings
      WHERE title = ${title} AND platform = ${platform}
        AND sub_category IS NOT NULL AND sub_category != ''
      GROUP BY sub_category
      ORDER BY cnt DESC
      LIMIT 1
    `,
    sql`
      SELECT reviewer_name, reviewer_info, body, rating,
             likes_count, is_spoiler, reviewed_at
      FROM reviews
      WHERE platform = ${platform} AND work_title = ${title}
      ORDER BY reviewed_at DESC NULLS LAST, collected_at DESC
      LIMIT 50
    `,
    sql`
      SELECT COUNT(*)::int as total
      FROM reviews
      WHERE platform = ${platform} AND work_title = ${title}
    `,
  ]);

  // 정확한 제목 매칭 실패 시, 정규화 매칭 시도 (대소문자/하이픈/아포스트로피 차이 대응)
  if (metaRows.length === 0) {
    const fuzzyRows = await sql`
      SELECT platform, title, title_kr, genre, genre_kr, is_riverse, url,
             thumbnail_url, thumbnail_base64,
             author, publisher, label, tags, description,
             hearts, favorites, rating, review_count,
             best_rank,
             first_seen_date::text as first_seen_date,
             last_seen_date::text as last_seen_date
      FROM works
      WHERE platform = ${platform}
        AND (LOWER(REGEXP_REPLACE(title, '[^a-zA-Z0-9]', '', 'g'))
              = LOWER(REGEXP_REPLACE(${title}, '[^a-zA-Z0-9]', '', 'g'))
             OR LEFT(LOWER(REGEXP_REPLACE(title, '[^a-zA-Z0-9]', '', 'g')), 20)
              = LEFT(LOWER(REGEXP_REPLACE(${title}, '[^a-zA-Z0-9]', '', 'g')), 20))
      LIMIT 1
    `;
    if (fuzzyRows.length === 0) {
      notFound();
    }
    // 정규화 매칭 성공 → 올바른 제목 페이지로 리다이렉트
    const { redirect } = await import("next/navigation");
    redirect(`/title/${platform}/${encodeURIComponent(fuzzyRows[0].title)}`);
  }

  const w = metaRows[0];
  const metadata = {
    platform: String(w.platform),
    title: String(w.title),
    title_kr: String(w.title_kr || ""),
    genre: String(w.genre || ""),
    genre_kr: String(w.genre_kr || ""),
    is_riverse: Boolean(w.is_riverse ?? false),
    url: String(w.url || ""),
    thumbnail_url: w.thumbnail_url ? String(w.thumbnail_url) : null,
    thumbnail_base64: w.thumbnail_base64 ? String(w.thumbnail_base64) : null,
    author: String(w.author || ""),
    publisher: String(w.publisher || ""),
    label: String(w.label || ""),
    tags: String(w.tags || ""),
    description: String(w.description || ""),
    hearts: w.hearts != null ? Number(w.hearts) : null,
    favorites: w.favorites != null ? Number(w.favorites) : null,
    rating: w.rating ? Number(w.rating) : null,
    review_count: w.review_count != null ? Number(w.review_count) : null,
    best_rank: w.best_rank != null ? Number(w.best_rank) : null,
    first_seen_date: w.first_seen_date ? String(w.first_seen_date) : null,
    last_seen_date: w.last_seen_date ? String(w.last_seen_date) : null,
  };

  const genre = genreRows.length > 0 ? genreRows[0].sub_category : "";

  // 2단계: 장르순위 + 크로스플랫폼을 병렬 조회
  const titleKr = metadata.title_kr;
  const [genreRankRows, crossPlatformRows] = await Promise.all([
    genre
      ? sql`
          SELECT date::text as date, rank::int as rank
          FROM rankings
          WHERE title = ${title} AND platform = ${platform}
            AND sub_category = ${genre}
          ORDER BY date DESC
          LIMIT 90
        `
      : Promise.resolve([]),
    titleKr
      ? sql`
          SELECT w.platform, w.title, w.best_rank, w.rating, w.review_count, w.last_seen_date
          FROM works w
          WHERE w.platform != ${platform}
            AND (w.title = ${title} OR (w.title_kr = ${titleKr} AND w.title_kr != ''))
          ORDER BY w.platform
        `
      : sql`
          SELECT w.platform, w.title, w.best_rank, w.rating, w.review_count, w.last_seen_date
          FROM works w
          WHERE w.platform != ${platform} AND w.title = ${title}
          ORDER BY w.platform
        `,
  ]);

  // 장르 히스토리 구성 (date/rank를 명시적으로 변환)
  const genreRankMap: Record<string, number> = {};
  for (const r of genreRankRows) {
    genreRankMap[String(r.date)] = Number(r.rank);
  }

  const allDates = new Set<string>();
  for (const r of overallRows) allDates.add(String(r.date));
  for (const d of Object.keys(genreRankMap)) allDates.add(d);

  const overallMap: Record<string, number> = {};
  for (const r of overallRows) overallMap[String(r.date)] = Number(r.rank);

  const history = Array.from(allDates)
    .sort()
    .map((date) => ({
      date,
      rank: overallMap[date] ?? null,
      genre_rank: genreRankMap[date] ?? null,
    }));

  // 크로스플랫폼 최신 순위 + 랭킹 히스토리
  const crossPlatform = await Promise.all(
    crossPlatformRows.map(async (cp) => {
      const [latestRankRows, historyRows] = await Promise.all([
        sql`
          SELECT rank::int as rank, date::text as date
          FROM rankings
          WHERE title = ${cp.title} AND platform = ${cp.platform}
            AND COALESCE(sub_category, '') = ''
          ORDER BY date DESC
          LIMIT 1
        `,
        sql`
          SELECT date::text as date, rank::int as rank
          FROM rankings
          WHERE title = ${cp.title} AND platform = ${cp.platform}
            AND COALESCE(sub_category, '') = ''
          ORDER BY date DESC
          LIMIT 90
        `,
      ]);
      const cpPlatform = PLATFORMS.find((p) => p.id === cp.platform);
      return {
        platform: String(cp.platform),
        platform_name: cpPlatform?.name || String(cp.platform),
        platform_color: cpPlatform?.color || "#666",
        best_rank: cp.best_rank != null ? Number(cp.best_rank) : null,
        latest_rank: latestRankRows.length > 0 ? Number(latestRankRows[0].rank) : null,
        latest_date: latestRankRows.length > 0 ? String(latestRankRows[0].date) : null,
        rating: cp.rating ? Number(cp.rating) : null,
        review_count: cp.review_count != null ? Number(cp.review_count) : null,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        rank_history: historyRows.map((r: any) => ({
          date: String(r.date),
          rank: Number(r.rank),
        })),
      };
    })
  );

  // 리뷰 처리 (Date 객체를 문자열로 변환하여 직렬화 보장)
  const reviews = reviewRows.map((r) => ({
    reviewer_name: String(r.reviewer_name || ""),
    reviewer_info: String(r.reviewer_info || ""),
    body: String(r.body || ""),
    rating: r.rating != null ? Number(r.rating) : null,
    likes_count: Number(r.likes_count ?? 0),
    is_spoiler: Boolean(r.is_spoiler ?? false),
    reviewed_at: r.reviewed_at
      ? new Date(r.reviewed_at).toISOString().split("T")[0]
      : null,
  }));

  const totalReviews = reviewCountRows[0]?.total || 0;

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

  const data = {
    metadata,
    rankHistory: { overall: history, genre },
    crossPlatform,
    reviewStats: {
      total: totalReviews,
      avg_rating: avgRating ? Math.round(avgRating * 10) / 10 : null,
      rating_distribution: ratingDistribution,
    },
    reviews,
  };

  return <TitleDetailClient data={data} />;
}
