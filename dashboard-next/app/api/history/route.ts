import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const title = searchParams.get("title") || "";
  const platform = searchParams.get("platform") || "";
  const days = parseInt(searchParams.get("days") || "30", 10);

  if (!title || !platform) {
    return NextResponse.json({ error: "title and platform required" }, { status: 400 });
  }

  // 1. 종합순위 (sub_category = '')
  const overallRows = await sql`
    SELECT date, rank::int as rank
    FROM rankings
    WHERE title = ${title} AND platform = ${platform}
      AND COALESCE(sub_category, '') = ''
    ORDER BY date DESC
    LIMIT ${days}
  `;

  // 2. 이 작품의 장르 sub_category 찾기
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

  // 3. 장르순위
  let genreRankMap: Record<string, number> = {};
  if (genre) {
    const genreRankRows = await sql`
      SELECT date, rank::int as rank
      FROM rankings
      WHERE title = ${title} AND platform = ${platform}
        AND sub_category = ${genre}
      ORDER BY date DESC
      LIMIT ${days}
    `;
    for (const r of genreRankRows) {
      genreRankMap[r.date] = r.rank;
    }
  }

  // 4. 날짜 합치기 (종합 + 장르 모든 날짜)
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

  return NextResponse.json({ overall: history, genre });
}
