import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";
import { PLATFORMS } from "@/lib/constants";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const date = searchParams.get("date") || "";

  if (!date) {
    return NextResponse.json({ error: "date required" }, { status: 400 });
  }

  // 각 플랫폼의 "종합" sub_category 키 목록 (대부분 '', Asura는 'all')
  const overallKeys = PLATFORMS.map((p) => p.genres[0]?.key ?? "");
  const allOverallKeys = [...new Set(overallKeys)];

  const rows = await sql`
    SELECT
      platform,
      COUNT(*)::int as total,
      COUNT(*) FILTER (WHERE is_riverse = TRUE)::int as riverse
    FROM rankings
    WHERE date = ${date} AND COALESCE(sub_category, '') = ANY(${allOverallKeys})
    GROUP BY platform
  `;

  const stats: Record<string, { total: number; riverse: number }> = {};
  for (const r of rows) {
    stats[r.platform] = { total: r.total, riverse: r.riverse };
  }

  return NextResponse.json(stats, {
    headers: {
      "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600",
    },
  });
}
