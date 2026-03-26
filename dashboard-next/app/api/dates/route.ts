import { NextResponse } from "next/server";
import { sql } from "@/lib/supabase";

export async function GET() {
  const rows = await sql`
    SELECT date, MAX(created_at) as last_updated
    FROM rankings
    GROUP BY date
    ORDER BY date DESC
  `;
  const dates = rows.map((r) => r.date);
  const lastUpdated: Record<string, string> = {};
  for (const r of rows) {
    lastUpdated[r.date] = r.last_updated;
  }
  return NextResponse.json({ dates, lastUpdated }, {
    headers: {
      "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600",
    },
  });
}
