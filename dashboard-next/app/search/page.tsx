import { SearchClient } from "@/components/search-client";
import { sql } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export default async function SearchPage() {
  // 최신 날짜 가져오기
  const dateRows = await sql`SELECT DISTINCT date::text as date FROM rankings ORDER BY date DESC LIMIT 1`;
  const latestDate = dateRows.length > 0 ? String(dateRows[0].date) : "";

  return <SearchClient latestDate={latestDate} />;
}
