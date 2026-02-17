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

  const rows = await sql`
    SELECT date, MIN(rank)::int as rank
    FROM rankings
    WHERE title = ${title} AND platform = ${platform}
    GROUP BY date
    ORDER BY date DESC
    LIMIT ${days}
  `;

  const history = rows
    .map((r) => ({ date: r.date, rank: r.rank }))
    .reverse();

  return NextResponse.json(history);
}
