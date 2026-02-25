import { sql } from "@/lib/supabase";
import type { Ranking, PlatformStats } from "@/lib/types";
import { DashboardClient } from "@/components/dashboard-client";
import { PLATFORMS } from "@/lib/constants";
import { unstable_cache } from "next/cache";

// 동적 렌더링 강제 (빌드 시 DB 연결 불가)
export const dynamic = "force-dynamic";

// 초기 데이터를 캐시하여 반복 요청 시 DB 재조회 방지 (5분)
const getInitialData = unstable_cache(
  async () => {
    const defaultPlatform = "piccoma";

    // 1. 날짜 목록 조회
    const dateRows = await sql`SELECT DISTINCT date::text as date FROM rankings ORDER BY date DESC`;
    const dates: string[] = dateRows.map((r) => String(r.date));
    const latestDate = dates[0] || "";

    if (!latestDate) {
      return { dates, latestDate, stats: {} as Record<string, PlatformStats>, riverseCounts: {} as Record<string, number>, rankings: [] as Ranking[], defaultPlatform };
    }

    // 2. 통계 + 리버스카운트 + 랭킹 + 이전날짜를 병렬 조회
    // 각 플랫폼의 "종합" sub_category 키 목록 (대부분 '', Asura는 'all')
    const overallKeys = [...new Set(PLATFORMS.map((p) => p.genres[0]?.key ?? ""))];

    const [statsRows, riverseCountRows, rankingRows, prevDateRows] = await Promise.all([
      sql`
        SELECT platform, COUNT(*)::int as total,
               COUNT(*) FILTER (WHERE is_riverse = TRUE)::int as riverse
        FROM rankings
        WHERE date = ${latestDate} AND COALESCE(sub_category, '') = ANY(${overallKeys})
        GROUP BY platform
      `,
      sql`
        SELECT COALESCE(sub_category, '') as sub_category, COUNT(*)::int as count
        FROM rankings
        WHERE date = ${latestDate} AND platform = ${defaultPlatform} AND is_riverse = TRUE
        GROUP BY COALESCE(sub_category, '')
      `,
      sql`
        SELECT rank::int as rank, title, title_kr, genre, genre_kr, url, is_riverse
        FROM rankings
        WHERE date = ${latestDate} AND platform = ${defaultPlatform} AND COALESCE(sub_category, '') = ''
        ORDER BY rank
      `,
      sql`
        SELECT DISTINCT date::text as date FROM rankings
        WHERE date < ${latestDate} AND platform = ${defaultPlatform}
        ORDER BY date DESC LIMIT 1
      `,
    ]);

    const stats: Record<string, PlatformStats> = {};
    for (const r of statsRows) {
      stats[r.platform] = { total: r.total, riverse: r.riverse };
    }

    const riverseCounts: Record<string, number> = {};
    for (const r of riverseCountRows) {
      riverseCounts[r.sub_category] = r.count;
    }

    // 3. 랭킹 변동 + 썸네일을 병렬 조회
    const titles = rankingRows.map((r) => r.title);
    const [prevRankings, thumbRows] = await Promise.all([
      prevDateRows.length > 0
        ? sql`
            SELECT title, rank::int as rank FROM rankings
            WHERE date = ${prevDateRows[0].date} AND platform = ${defaultPlatform}
              AND COALESCE(sub_category, '') = ''
              AND title = ANY(${titles})
          `
        : Promise.resolve([]),
      titles.length > 0
        ? sql`
            SELECT title, thumbnail_url, unified_work_id
            FROM works
            WHERE platform = ${defaultPlatform}
              AND title = ANY(${titles})
          `
        : Promise.resolve([]),
    ]);

    const rankChanges: Record<string, number> = {};
    if (prevRankings.length > 0) {
      const prevMap: Record<string, number> = {};
      for (const r of prevRankings) prevMap[r.title] = r.rank;
      for (const r of rankingRows) {
        rankChanges[r.title] = r.title in prevMap ? prevMap[r.title] - r.rank : 999;
      }
    }

    const thumbnails: Record<string, string> = {};
    const unifiedIds: Record<string, number> = {};
    for (const t of thumbRows) {
      if (t.thumbnail_url) thumbnails[t.title] = t.thumbnail_url;
      if (t.unified_work_id) unifiedIds[t.title] = t.unified_work_id;
    }

    const rankings: Ranking[] = rankingRows.map((r) => ({
      rank: r.rank,
      title: r.title,
      title_kr: r.title_kr || null,
      genre: r.genre || null,
      genre_kr: r.genre_kr || null,
      url: r.url,
      is_riverse: r.is_riverse,
      rank_change: rankChanges[r.title] ?? 0,
      thumbnail_url: thumbnails[r.title] || undefined,
      unified_work_id: unifiedIds[r.title] || null,
    }));

    return { dates, latestDate, stats, riverseCounts, rankings, defaultPlatform };
  },
  ["home-initial-data"],
  { revalidate: 300 } // 5분 캐시
);

export default async function Home() {
  const { dates, latestDate, stats, riverseCounts, rankings, defaultPlatform } = await getInitialData();

  if (!latestDate) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">데이터가 없습니다.</p>
      </div>
    );
  }

  return (
    <DashboardClient
      initialDates={dates}
      initialDate={latestDate}
      initialStats={stats}
      initialRiverseCounts={riverseCounts}
      initialRankings={rankings}
      initialPlatform={defaultPlatform}
    />
  );
}
