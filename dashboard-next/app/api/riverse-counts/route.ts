import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const date = searchParams.get("date") || "";
  const platform = searchParams.get("platform") || "";

  if (!date || !platform) {
    return NextResponse.json({ error: "date and platform required" }, { status: 400 });
  }

  const rows = await sql`
    SELECT COALESCE(sub_category, '') as sub_category, COUNT(*)::int as count
    FROM rankings
    WHERE date = ${date} AND platform = ${platform} AND is_riverse = TRUE
    GROUP BY COALESCE(sub_category, '')
  `;

  const counts: Record<string, number> = {};
  for (const r of rows) {
    counts[r.sub_category] = r.count;
  }

  return NextResponse.json(counts, {
    headers: {
      "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600",
    },
  });
}
