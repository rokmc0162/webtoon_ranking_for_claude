import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";

/**
 * 작품 검색 API — 크로스 플랫폼 랭킹 조회
 *
 * GET /api/search?q=작품명&date=2026-02-25
 *
 * 작품명으로 검색하여 각 플랫폼별 랭킹 정보를 반환합니다.
 * - works 테이블에서 작품 메타데이터 검색
 * - rankings 테이블에서 해당 날짜의 랭킹 정보 조회
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const query = searchParams.get("q") || "";
  const date = searchParams.get("date") || "";

  if (!query || query.length < 2) {
    return NextResponse.json({ error: "검색어는 2자 이상 필요합니다" }, { status: 400 });
  }

  try {
    // 날짜 미지정 시 최신 날짜 사용
    let targetDate = date;
    if (!targetDate) {
      const dateRows = await sql`SELECT DISTINCT date::text as date FROM rankings ORDER BY date DESC LIMIT 1`;
      targetDate = dateRows.length > 0 ? String(dateRows[0].date) : "";
    }

    if (!targetDate) {
      return NextResponse.json({ results: [], date: "" });
    }

    // 작품 검색 (ILIKE + 한국어 제목도 검색)
    const searchPattern = `%${query}%`;

    // 1. rankings에서 해당 날짜의 매칭 작품 + 랭킹 정보 조회
    const rankingRows = await sql`
      SELECT
        r.platform,
        r.title,
        r.title_kr,
        r.rank::int as rank,
        r.genre,
        r.genre_kr,
        r.url,
        r.is_riverse,
        COALESCE(r.sub_category, '') as sub_category,
        w.thumbnail_url
      FROM rankings r
      LEFT JOIN works w ON w.platform = r.platform AND w.title = r.title
      WHERE r.date = ${targetDate}
        AND COALESCE(r.sub_category, '') = ''
        AND (
          r.title ILIKE ${searchPattern}
          OR r.title_kr ILIKE ${searchPattern}
        )
      ORDER BY r.platform, r.rank
    `;

    // 2. 결과를 작품별로 그룹핑
    const titleMap = new Map<string, {
      title: string;
      title_kr: string | null;
      thumbnail_url: string | null;
      is_riverse: boolean;
      platforms: Array<{
        platform: string;
        rank: number;
        genre: string | null;
        genre_kr: string | null;
        url: string | null;
      }>;
    }>();

    for (const row of rankingRows) {
      // 같은 작품명을 키로 그룹핑 (대소문자 무시)
      const normalizedTitle = String(row.title).toLowerCase();

      if (!titleMap.has(normalizedTitle)) {
        titleMap.set(normalizedTitle, {
          title: String(row.title),
          title_kr: row.title_kr ? String(row.title_kr) : null,
          thumbnail_url: row.thumbnail_url ? String(row.thumbnail_url) : null,
          is_riverse: Boolean(row.is_riverse),
          platforms: [],
        });
      }

      const entry = titleMap.get(normalizedTitle)!;
      entry.platforms.push({
        platform: String(row.platform),
        rank: Number(row.rank),
        genre: row.genre ? String(row.genre) : null,
        genre_kr: row.genre_kr ? String(row.genre_kr) : null,
        url: row.url ? String(row.url) : null,
      });

      // 한국어 제목이 없는 경우 업데이트
      if (!entry.title_kr && row.title_kr) {
        entry.title_kr = String(row.title_kr);
      }
      // 썸네일이 없는 경우 업데이트
      if (!entry.thumbnail_url && row.thumbnail_url) {
        entry.thumbnail_url = String(row.thumbnail_url);
      }
      // 리버스 여부 업데이트
      if (row.is_riverse) {
        entry.is_riverse = true;
      }
    }

    // 3. 결과 배열로 변환 (플랫폼 수 내림차순 정렬)
    const results = Array.from(titleMap.values())
      .sort((a, b) => {
        // 플랫폼 수가 많은 순 → 최고 랭킹 순
        if (b.platforms.length !== a.platforms.length) {
          return b.platforms.length - a.platforms.length;
        }
        const bestA = Math.min(...a.platforms.map(p => p.rank));
        const bestB = Math.min(...b.platforms.map(p => p.rank));
        return bestA - bestB;
      });

    return NextResponse.json({
      results,
      date: targetDate,
      query,
      total: results.length,
    });
  } catch (error) {
    console.error("Search error:", error);
    return NextResponse.json({ error: "검색 중 오류가 발생했습니다" }, { status: 500 });
  }
}
