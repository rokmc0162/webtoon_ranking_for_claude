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

  // 1. 작품 메타데이터 (works 테이블)
  const metaRows = await sql`
    SELECT platform, title, title_kr, genre, genre_kr, is_riverse, url,
           thumbnail_url, thumbnail_base64,
           author, publisher, label, tags, description,
           hearts, favorites, rating, review_count,
           best_rank, first_seen_date, last_seen_date
    FROM works
    WHERE platform = ${platform} AND title = ${title}
    LIMIT 1
  `;

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

  // 2. 랭킹 히스토리 (기존 history API 로직)
  const overallRows = await sql`
    SELECT date, rank::int as rank
    FROM rankings
    WHERE title = ${title} AND platform = ${platform}
      AND COALESCE(sub_category, '') = ''
    ORDER BY date DESC
    LIMIT 90
  `;

  const genreRows = await sql`
    SELECT sub_category, COUNT(*)::int as cnt
    FROM rankings
    WHERE title = ${title} AND platform = ${platform}
      AND sub_category IS NOT NULL AND sub_category != ''
    GROUP BY sub_category
    ORDER BY cnt DESC
    LIMIT 1
  `;

  const genre = genreRows.length > 0 ? genreRows[0].sub_category : "";

  let genreRankMap: Record<string, number> = {};
  if (genre) {
    const genreRankRows = await sql`
      SELECT date, rank::int as rank
      FROM rankings
      WHERE title = ${title} AND platform = ${platform}
        AND sub_category = ${genre}
      ORDER BY date DESC
      LIMIT 90
    `;
    for (const r of genreRankRows) {
      genreRankMap[r.date] = r.rank;
    }
  }

  const allDates = new Set<string>();
  for (const r of overallRows) allDates.add(r.date);
  for (const d of Object.keys(genreRankMap)) allDates.add(d);

  const overallMap: Record<string, number> = {};
  for (const r of overallRows) overallMap[r.date] = r.rank;

  const history = Array.from(allDates)
    .sort()
    .map((date) => ({
      date,
      rank: overallMap[date] ?? null,
      genre_rank: genreRankMap[date] ?? null,
    }));

  // 3. 크로스 플랫폼 비교
  const titleKr = metadata.title_kr;
  let crossPlatformRows;

  if (titleKr) {
    crossPlatformRows = await sql`
      SELECT w.platform, w.title, w.best_rank, w.rating, w.review_count, w.last_seen_date
      FROM works w
      WHERE w.platform != ${platform}
        AND (w.title = ${title} OR (w.title_kr = ${titleKr} AND w.title_kr != ''))
      ORDER BY w.platform
    `;
  } else {
    crossPlatformRows = await sql`
      SELECT w.platform, w.title, w.best_rank, w.rating, w.review_count, w.last_seen_date
      FROM works w
      WHERE w.platform != ${platform} AND w.title = ${title}
      ORDER BY w.platform
    `;
  }

  // 각 크로스플랫폼 작품의 최신 순위 조회
  const crossPlatform = [];
  for (const cp of crossPlatformRows) {
    const latestRankRows = await sql`
      SELECT rank::int as rank, date
      FROM rankings
      WHERE title = ${cp.title} AND platform = ${cp.platform}
        AND COALESCE(sub_category, '') = ''
      ORDER BY date DESC
      LIMIT 1
    `;
    const cpPlatform = PLATFORMS.find((p) => p.id === cp.platform);
    crossPlatform.push({
      platform: cp.platform,
      platform_name: cpPlatform?.name || cp.platform,
      best_rank: cp.best_rank ?? null,
      latest_rank: latestRankRows.length > 0 ? latestRankRows[0].rank : null,
      latest_date: latestRankRows.length > 0 ? latestRankRows[0].date : null,
      rating: cp.rating ? Number(cp.rating) : null,
      review_count: cp.review_count ?? null,
    });
  }

  // 4. 리뷰 통계 + 리뷰 목록
  const reviewRows = await sql`
    SELECT reviewer_name, reviewer_info, body, rating,
           likes_count, is_spoiler, reviewed_at
    FROM reviews
    WHERE platform = ${platform} AND work_title = ${title}
    ORDER BY reviewed_at DESC NULLS LAST, collected_at DESC
  `;

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

  // 리뷰 통계 계산
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

  return NextResponse.json({
    metadata,
    rankHistory: { overall: history, genre },
    crossPlatform,
    reviewStats: {
      total: reviews.length,
      avg_rating: avgRating ? Math.round(avgRating * 10) / 10 : null,
      rating_distribution: ratingDistribution,
    },
    reviews,
  });
}
