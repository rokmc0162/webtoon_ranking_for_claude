import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";
import { getPlatformById } from "@/lib/constants";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const title = searchParams.get("title") || "";
  const platform = searchParams.get("platform") || "";
  const days = parseInt(searchParams.get("days") || "30", 10);

  if (!title || !platform) {
    return NextResponse.json({ error: "title and platform required" }, { status: 400 });
  }

  // 1+2 병렬: 종합순위 + 장르 sub_category 동시 조회
  const [overallRows, genreRows] = await Promise.all([
    sql`
      SELECT date, rank::int as rank
      FROM rankings
      WHERE title = ${title} AND platform = ${platform}
        AND COALESCE(sub_category, '') = ''
      ORDER BY date DESC
      LIMIT ${days}
    `,
    sql`
      SELECT sub_category, COUNT(*)::int as cnt
      FROM rankings
      WHERE title = ${title} AND platform = ${platform}
        AND sub_category IS NOT NULL AND sub_category != ''
      GROUP BY sub_category
      ORDER BY cnt DESC
    `,
  ]);

  // 3. 전체 장르 순위 벌크 조회
  const platformInfo = getPlatformById(platform);
  let genreRankRows: { sub_category: string; date: string; rank: number }[] = [];
  if (genreRows.length > 0) {
    genreRankRows = await sql`
      SELECT sub_category, date, rank::int as rank
      FROM rankings
      WHERE title = ${title} AND platform = ${platform}
        AND sub_category IS NOT NULL AND sub_category != ''
      ORDER BY sub_category, date DESC
    `;
  }

  // 장르별 히스토리 분류
  const genreHistMap = new Map<string, { date: string; rank: number }[]>();
  for (const r of genreRankRows) {
    const sc = String(r.sub_category);
    if (!genreHistMap.has(sc)) genreHistMap.set(sc, []);
    const arr = genreHistMap.get(sc)!;
    if (arr.length < days) arr.push({ date: String(r.date), rank: Number(r.rank) });
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
  const overall = overallRows
    .map((r) => ({ date: String(r.date), rank: Number(r.rank) }))
    .reverse();

  return NextResponse.json({ overall, genres }, {
    headers: {
      "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600",
    },
  });
}
