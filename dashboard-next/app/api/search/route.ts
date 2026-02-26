import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";

/**
 * 작품 검색 API — 전체 작품 DB에서 검색
 *
 * GET /api/search?q=작품명
 *
 * unified_works + works에서 한/일/영 제목으로 검색
 * 클릭 시 /work/[id] 통합 분석 페이지로 이동
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const query = searchParams.get("q") || "";

  if (!query || query.length < 2) {
    return NextResponse.json({ error: "검색어는 2자 이상 필요합니다" }, { status: 400 });
  }

  try {
    const searchPattern = `%${query}%`;

    // unified_works에서 한/일/영 제목 + 작가명으로 검색
    // works JOIN으로 플랫폼별 정보도 함께 가져옴
    const rows = await sql`
      SELECT
        uw.id,
        uw.title_kr,
        uw.title_en,
        uw.title_canonical,
        uw.author,
        uw.genre_kr,
        uw.is_riverse,
        uw.thumbnail_url AS uw_thumb,
        json_agg(json_build_object(
          'platform', w.platform,
          'title', w.title,
          'best_rank', w.best_rank,
          'rating', w.rating,
          'review_count', w.review_count,
          'thumbnail_url', w.thumbnail_url,
          'last_seen_date', w.last_seen_date
        ) ORDER BY w.platform) AS works
      FROM unified_works uw
      LEFT JOIN works w ON w.unified_work_id = uw.id
      WHERE
        uw.title_kr ILIKE ${searchPattern}
        OR uw.title_canonical ILIKE ${searchPattern}
        OR uw.title_en ILIKE ${searchPattern}
        OR uw.author ILIKE ${searchPattern}
      GROUP BY uw.id
      ORDER BY
        -- 리버스 우선
        uw.is_riverse DESC,
        -- 플랫폼 수 많은 순
        COUNT(w.platform) DESC,
        -- 이름 순
        uw.title_kr
      LIMIT 50
    `;

    const results = rows.map((r) => ({
      id: r.id,
      title_kr: r.title_kr || "",
      title_en: r.title_en || "",
      title_canonical: r.title_canonical || "",
      author: r.author || "",
      genre_kr: r.genre_kr || "",
      is_riverse: r.is_riverse ?? false,
      thumbnail_url: r.uw_thumb || null,
      works: (r.works || [])
        .filter((w: Record<string, unknown>) => w.platform !== null)
        .map((w: Record<string, unknown>) => ({
          platform: String(w.platform),
          title: String(w.title || ""),
          best_rank: w.best_rank != null ? Number(w.best_rank) : null,
          rating: w.rating != null ? Number(w.rating) : null,
          review_count: w.review_count != null ? Number(w.review_count) : null,
          thumbnail_url: w.thumbnail_url ? String(w.thumbnail_url) : null,
          last_seen_date: w.last_seen_date ? String(w.last_seen_date) : null,
        })),
    }));

    // thumbnail_url 보정: unified_works에 없으면 works에서 가져옴
    for (const r of results) {
      if (!r.thumbnail_url && r.works.length > 0) {
        const thumb = r.works.find((w: { thumbnail_url: string | null }) => w.thumbnail_url);
        if (thumb) r.thumbnail_url = thumb.thumbnail_url;
      }
    }

    return NextResponse.json({
      results,
      query,
      total: results.length,
    }, {
      headers: {
        "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600",
      },
    });
  } catch (error) {
    console.error("Search error:", error);
    return NextResponse.json({ error: "검색 중 오류가 발생했습니다" }, { status: 500 });
  }
}
