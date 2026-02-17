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

  // 현재 랭킹
  const rankings = await sql`
    SELECT rank, title, title_kr, genre, genre_kr, url, is_riverse
    FROM rankings
    WHERE date = ${date} AND platform = ${platform} AND COALESCE(sub_category, '') = ${subCategory}
    ORDER BY rank
  `;

  // 이전 날짜 찾기
  const prevDateRows = await sql`
    SELECT DISTINCT date FROM rankings
    WHERE date < ${date} AND platform = ${platform}
    ORDER BY date DESC LIMIT 1
  `;

  let rankChanges: Record<string, number> = {};
  if (prevDateRows.length > 0) {
    const prevDate = prevDateRows[0].date;
    const prevRankings = await sql`
      SELECT title, rank FROM rankings
      WHERE date = ${prevDate} AND platform = ${platform}
    `;
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

  // 썸네일 로드
  const thumbRows = await sql`
    SELECT title, thumbnail_url, thumbnail_base64
    FROM works
    WHERE platform = ${platform}
      AND (thumbnail_url IS NOT NULL OR thumbnail_base64 IS NOT NULL)
  `;
  const thumbnails: Record<string, { url?: string; base64?: string }> = {};
  for (const t of thumbRows) {
    thumbnails[t.title] = {
      url: t.thumbnail_url || undefined,
      base64: t.thumbnail_base64 || undefined,
    };
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
    thumbnail_url: thumbnails[r.title]?.url || null,
    thumbnail_base64: thumbnails[r.title]?.base64 || null,
  }));

  return NextResponse.json(result);
}
