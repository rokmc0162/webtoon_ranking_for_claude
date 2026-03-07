import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";
import { PLATFORMS } from "@/lib/constants";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const idParam = searchParams.get("id");

  if (!idParam) {
    return NextResponse.json({ error: "id required" }, { status: 400 });
  }

  const id = parseInt(idParam, 10);
  if (isNaN(id)) {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  }

  // 1. unified_works 마스터 정보
  const [metaRows] = await Promise.all([
    sql`
      SELECT id, title_kr, title_canonical, author, artist, publisher,
             genre, genre_kr, tags, description, is_riverse,
             thumbnail_url, thumbnail_base64
      FROM unified_works
      WHERE id = ${id}
      LIMIT 1
    `,
  ]);

  if (metaRows.length === 0) {
    return NextResponse.json({ error: "work not found" }, { status: 404 });
  }

  const uw = metaRows[0];
  const metadata = {
    id: uw.id,
    title_kr: uw.title_kr || "",
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

  // 2. 모든 플랫폼별 works 조회
  const worksRows = await sql`
    SELECT platform, title, url, best_rank, rating, review_count,
           hearts, favorites, first_seen_date, last_seen_date,
           genre, thumbnail_url, thumbnail_base64
    FROM works
    WHERE unified_work_id = ${id}
    ORDER BY platform
  `;

  // 3. 모든 플랫폼의 장르 + 랭킹 히스토리를 벌크 쿼리로 조회
  const allTitles = worksRows.map((w) => w.title);
  const allPlatforms = worksRows.map((w) => w.platform);

  const [genreBulk, rankBulk] = await Promise.all([
    sql`
      SELECT title, platform, sub_category, COUNT(*)::int as cnt
      FROM rankings
      WHERE title = ANY(${allTitles}) AND platform = ANY(${allPlatforms})
        AND sub_category IS NOT NULL AND sub_category != ''
      GROUP BY title, platform, sub_category
      ORDER BY title, platform, cnt DESC
    `,
    sql`
      SELECT title, platform, sub_category, date, rank::int as rank
      FROM rankings
      WHERE title = ANY(${allTitles}) AND platform = ANY(${allPlatforms})
      ORDER BY title, platform, date DESC
    `,
  ]);

  // 장르 벌크 데이터를 플랫폼별로 정리
  const genreMap = new Map<string, { sub_category: string; cnt: number }[]>();
  for (const row of genreBulk) {
    const key = `${row.platform}:${row.title}`;
    if (!genreMap.has(key)) genreMap.set(key, []);
    const pInfo = PLATFORMS.find((p) => p.id === row.platform);
    const overallKey = pInfo?.genres[0]?.key ?? "";
    if (row.sub_category !== overallKey) {
      genreMap.get(key)!.push({ sub_category: row.sub_category, cnt: row.cnt });
    }
  }

  // 랭킹 벌크 데이터를 플랫폼별로 분류
  type RankEntry = { date: string; rank: number };
  const rankMap = new Map<string, { overall: RankEntry[]; genres: Map<string, RankEntry[]>; latest: RankEntry | null }>();

  for (const w of worksRows) {
    const pInfo = PLATFORMS.find((p) => p.id === w.platform);
    const overallKey = pInfo?.genres[0]?.key ?? "";
    const mapKey = `${w.platform}:${w.title}`;
    const genreKeys = (genreMap.get(mapKey) || []).map((g) => g.sub_category);

    const overall: RankEntry[] = [];
    const genreEntries = new Map<string, RankEntry[]>();
    for (const gk of genreKeys) genreEntries.set(gk, []);
    let latest: RankEntry | null = null;

    for (const r of rankBulk) {
      if (r.title !== w.title || r.platform !== w.platform) continue;
      const sc = r.sub_category || "";
      const entry = { date: String(r.date), rank: r.rank };

      if (overallKey === "" ? sc === "" : sc === overallKey) {
        if (overall.length < 90) overall.push(entry);
        if (!latest) latest = entry;
      }
      if (genreEntries.has(sc) && genreEntries.get(sc)!.length < 90) {
        genreEntries.get(sc)!.push(entry);
      }
    }

    rankMap.set(mapKey, { overall, genres: genreEntries, latest });
  }

  // 플랫폼 데이터 조립
  const platforms = worksRows.map((w) => {
    const pInfo = PLATFORMS.find((p) => p.id === w.platform);
    const mapKey = `${w.platform}:${w.title}`;
    const genres = genreMap.get(mapKey) || [];
    const ranks = rankMap.get(mapKey) || { overall: [], genres: new Map(), latest: null };

    const genreHistories = genres.map((g) => ({
      sub_category: g.sub_category,
      label: pInfo?.genres.find((gn) => gn.key === g.sub_category)?.label || g.sub_category,
      history: ranks.genres.get(g.sub_category) || [],
    }));

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
      first_seen_date: w.first_seen_date || null,
      last_seen_date: w.last_seen_date || null,
      rank_history: ranks.overall,
      genre_histories: genreHistories,
    };
  });

  // 4. 모든 플랫폼 리뷰 통합 (최대 50건)
  const titleList = worksRows.map((w) => w.title);
  const platformList = worksRows.map((w) => w.platform);

  // 모든 플랫폼-제목 조합에서 리뷰 조회
  const reviewRows =
    titleList.length > 0
      ? await sql`
          SELECT r.platform, r.work_title, r.reviewer_name, r.reviewer_info,
                 r.body, r.rating, r.likes_count, r.is_spoiler, r.reviewed_at
          FROM reviews r
          INNER JOIN works w ON w.platform = r.platform AND w.title = r.work_title
          WHERE w.unified_work_id = ${id}
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

  // 리뷰 통계
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
      platforms,
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
