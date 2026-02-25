import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const date = searchParams.get("date") || "";
  const platform = searchParams.get("platform") || "";
  const subCategory = searchParams.get("sub_category") || "";

  if (!date || !platform) {
    return NextResponse.json({ error: "date and platform required" }, { status: 400 });
  }

  // 모든 쿼리를 병렬로 실행
  const [rankings, prevDateRows] = await Promise.all([
    // 현재 랭킹
    sql`
      SELECT rank, title, title_kr, genre, genre_kr, url, is_riverse
      FROM rankings
      WHERE date = ${date} AND platform = ${platform} AND COALESCE(sub_category, '') = ${subCategory}
      ORDER BY rank
    `,
    // 이전 날짜 찾기
    sql`
      SELECT DISTINCT date FROM rankings
      WHERE date < ${date} AND platform = ${platform}
      ORDER BY date DESC LIMIT 1
    `,
  ]);

  // 랭킹 타이틀 목록으로 썸네일만 필터링 (전체 works 로드 대신)
  const titles = rankings.map((r) => r.title);

  // 이전 랭킹 & 썸네일을 병렬로 (타이틀 기반 필터)
  const [prevRankings, thumbRows] = await Promise.all([
    prevDateRows.length > 0
      ? sql`
          SELECT title, rank FROM rankings
          WHERE date = ${prevDateRows[0].date} AND platform = ${platform}
            AND COALESCE(sub_category, '') = ${subCategory}
            AND title = ANY(${titles})
        `
      : Promise.resolve([]),
    titles.length > 0
      ? sql`
          SELECT title, thumbnail_url, unified_work_id
          FROM works
          WHERE platform = ${platform}
            AND title = ANY(${titles})
        `
      : Promise.resolve([]),
  ]);

  // rank changes 계산
  const rankChanges: Record<string, number> = {};
  if (prevRankings.length > 0) {
    const prevMap: Record<string, number> = {};
    for (const r of prevRankings) {
      prevMap[r.title] = r.rank;
    }
    for (const r of rankings) {
      if (r.title in prevMap) {
        rankChanges[r.title] = prevMap[r.title] - r.rank;
      } else {
        rankChanges[r.title] = 999; // NEW
      }
    }
  }

  // thumbnails + unified_work_id map
  const thumbnails: Record<string, string> = {};
  const unifiedIds: Record<string, number> = {};
  for (const t of thumbRows) {
    if (t.thumbnail_url) {
      thumbnails[t.title] = t.thumbnail_url;
    }
    if (t.unified_work_id) {
      unifiedIds[t.title] = t.unified_work_id;
    }
  }

  // 잘린 제목(Asura 등) → works 테이블의 전체 제목과 매칭 안되는 경우 prefix LIKE 폴백
  const missingTitles = titles.filter((t) => !thumbnails[t]);
  if (missingTitles.length > 0) {
    const fallbackRows = await sql`
      SELECT w.title AS full_title, w.thumbnail_url, w.unified_work_id
      FROM works w
      WHERE w.platform = ${platform}
        AND EXISTS (
          SELECT 1 FROM unnest(${missingTitles}::text[]) AS t(short)
          WHERE w.title LIKE t.short || '%'
        )
    `;
    for (const fb of fallbackRows) {
      // 잘린 제목 → full_title 매핑
      const matchedShort = missingTitles.find((t) => fb.full_title.startsWith(t));
      if (matchedShort) {
        if (fb.thumbnail_url && !thumbnails[matchedShort]) {
          thumbnails[matchedShort] = fb.thumbnail_url;
        }
        if (fb.unified_work_id && !unifiedIds[matchedShort]) {
          unifiedIds[matchedShort] = fb.unified_work_id;
        }
      }
    }
  }

  const result = rankings.map((r) => ({
    rank: r.rank,
    title: r.title,
    title_kr: r.title_kr || null,
    genre: r.genre || null,
    genre_kr: r.genre_kr || null,
    url: r.url,
    is_riverse: r.is_riverse,
    rank_change: rankChanges[r.title] ?? 0,
    thumbnail_url: thumbnails[r.title] || null,
    unified_work_id: unifiedIds[r.title] || null,
  }));

  return NextResponse.json(result, {
    headers: {
      "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600",
    },
  });
}
