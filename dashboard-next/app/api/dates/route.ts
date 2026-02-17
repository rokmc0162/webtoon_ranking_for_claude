import { NextResponse } from "next/server";
import { sql } from "@/lib/supabase";

export async function GET() {
  const rows = await sql`
    SELECT DISTINCT date FROM rankings ORDER BY date DESC
  `;
  const dates = rows.map((r) => r.date);
  return NextResponse.json(dates);
}
