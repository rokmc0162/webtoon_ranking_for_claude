import { SearchClient } from "@/components/search-client";
import { sql } from "@/lib/supabase";

// ISR: 5분마다 재생성
export const revalidate = 300;

export default async function SearchPage() {
  try {
    const dateRows = await sql`SELECT DISTINCT date::text as date FROM rankings ORDER BY date DESC LIMIT 1`;
    const latestDate = dateRows.length > 0 ? String(dateRows[0].date) : "";
    return <SearchClient latestDate={latestDate} />;
  } catch {
    return <SearchClient latestDate="" />;
  }
}
