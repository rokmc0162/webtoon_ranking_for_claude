import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const date = searchParams.get("date") || "";

  if (!date) {
    return NextResponse.json({ error: "date required" }, { status: 400 });
  }

  const rows = await sql`
    SELECT
      platform,
      COUNT(*)::int as total,
      COUNT(*) FILTER (WHERE is_riverse = TRUE)::int as riverse
    FROM rankings
    WHERE date = ${date} AND COALESCE(sub_category, '') = ''
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
