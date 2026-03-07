import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";
import { PLATFORMS } from "@/lib/constants";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const platform = searchParams.get("platform") || "";
  const title = searchParams.get("title") || "";

  if (!platform || !title) {
    return NextResponse.json(
      { error: "platform and title required" },
      { status: 400 }
    );
  }

  const platformInfo = PLATFORMS.find((p) => p.id === platform);

  // 1단계: 메타데이터 + 랭킹히스토리 + 장르(전체) + 리뷰를 병렬 조회
  const [metaRows, overallRows, genreRows, reviewRows] = await Promise.all([
    sql`
      SELECT platform, title, title_kr, genre, genre_kr, is_riverse, url,
             thumbnail_url, thumbnail_base64,
             author, publisher, label, tags, description,
             hearts, favorites, rating, review_count,
             best_rank, first_seen_date, last_seen_date
      FROM works
      WHERE platform = ${platform} AND title = ${title}
      LIMIT 1
    `,
    sql`
      SELECT date, rank::int as rank
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
    `,
    sql`
      SELECT reviewer_name, reviewer_info, body, rating,
             likes_count, is_spoiler, reviewed_at
      FROM reviews
      WHERE platform = ${platform} AND work_title = ${title}
      ORDER BY reviewed_at DESC NULLS LAST, collected_at DESC
      LIMIT 50
    `,
  ]);

  if (metaRows.length === 0) {
    return NextResponse.json({ error: "title not found" }, { status: 404 });
  }

  const w = metaRows[0];
  const metadata = {
    platform: w.platform,
    title: w.title,
    title_kr: w.title_kr || "",
    genre: w.genre || "",
    genre_kr: w.genre_kr || "",
    is_riverse: w.is_riverse ?? false,
    url: w.url || "",
    thumbnail_url: w.thumbnail_url || null,
    thumbnail_base64: w.thumbnail_base64 || null,
    author: w.author || "",
    publisher: w.publisher || "",
    label: w.label || "",
    tags: w.tags || "",
    description: w.description || "",
    hearts: w.hearts ?? null,
    favorites: w.favorites ?? null,
    rating: w.rating ? Number(w.rating) : null,
    review_count: w.review_count ?? null,
    best_rank: w.best_rank ?? null,
    first_seen_date: w.first_seen_date || null,
    last_seen_date: w.last_seen_date || null,
  };

  const hasGenres = genreRows.length > 0;

  // 2단계: 장르 히스토리(벌크) + 크로스플랫폼을 병렬 조회
  const titleKr = metadata.title_kr;
  const [genreRankRows, crossPlatformRows] = await Promise.all([
    hasGenres
      ? sql`
          SELECT sub_category, date::text as date, rank::int as rank
          FROM rankings
          WHERE title = ${title} AND platform = ${platform}
            AND sub_category IS NOT NULL AND sub_category != ''
          ORDER BY sub_category, date DESC
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

  // 장르별 히스토리 분류
  const genreHistMap = new Map<string, { date: string; rank: number }[]>();
  for (const r of genreRankRows) {
    const sc = String(r.sub_category);
    if (!genreHistMap.has(sc)) genreHistMap.set(sc, []);
    const arr = genreHistMap.get(sc)!;
    if (arr.length < 90) arr.push({ date: String(r.date), rank: Number(r.rank) });
  }

  const genres = genreRows.map((g) => {
    const sc = String(g.sub_category);
    return {
      sub_category: sc,
      label: platformInfo?.genres.find((gn) => gn.key === sc)?.label || sc,
      history: (genreHistMap.get(sc) || []).reverse(),
    };
  });

  // 종합 히스토리
  const history = overallRows
    .map((r) => ({ date: String(r.date), rank: Number(r.rank) }))
    .reverse();

  // 크로스플랫폼 최신 순위 + 랭킹 히스토리: 병렬 실행
  const crossPlatform = await Promise.all(
    crossPlatformRows.map(async (cp) => {
      const [latestRankRows, historyRows] = await Promise.all([
        sql`
          SELECT rank::int as rank, date
          FROM rankings
          WHERE title = ${cp.title} AND platform = ${cp.platform}
            AND COALESCE(sub_category, '') = ''
          ORDER BY date DESC
          LIMIT 1
        `,
        sql`
          SELECT date, rank::int as rank
          FROM rankings
          WHERE title = ${cp.title} AND platform = ${cp.platform}
            AND COALESCE(sub_category, '') = ''
          ORDER BY date DESC
          LIMIT 90
        `,
      ]);
      const cpPlatform = PLATFORMS.find((p) => p.id === cp.platform);
      return {
        platform: cp.platform,
        platform_name: cpPlatform?.name || cp.platform,
        platform_color: cpPlatform?.color || "#666",
        best_rank: cp.best_rank ?? null,
        latest_rank: latestRankRows.length > 0 ? latestRankRows[0].rank : null,
        latest_date: latestRankRows.length > 0 ? latestRankRows[0].date : null,
        rating: cp.rating ? Number(cp.rating) : null,
        review_count: cp.review_count ?? null,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        rank_history: historyRows.map((r: any) => ({
          date: r.date as string,
          rank: r.rank as number,
        })),
      };
    })
  );

  // 리뷰 통계 계산
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

  return NextResponse.json(
    {
      metadata,
      rankHistory: { overall: history, genres },
      crossPlatform,
      reviewStats: {
        total: reviews.length,
        avg_rating: avgRating ? Math.round(avgRating * 10) / 10 : null,
        rating_distribution: ratingDistribution,
      },
      reviews,
    },
    {
      headers: {
        "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600",
      },
    }
  );
}
