import { sql } from "@/lib/supabase";
import type { Ranking, PlatformStats } from "@/lib/types";
import { DashboardClient } from "@/components/dashboard-client";

// 동적 렌더링 강제 (빌드 시 DB 연결 불가)
export const dynamic = "force-dynamic";

// 서버 컴포넌트: 초기 데이터를 서버에서 직접 DB 조회 → API 워터폴 제거
export default async function Home() {
  const defaultPlatform = "piccoma";

  // 1. 날짜 목록 조회 (date를 text로 캐스트하여 Date 객체 방지)
  const dateRows = await sql`SELECT DISTINCT date::text as date FROM rankings ORDER BY date DESC`;
  const dates: string[] = dateRows.map((r) => String(r.date));
  const latestDate = dates[0] || "";

  if (!latestDate) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">데이터가 없습니다.</p>
      </div>
    );
  }

  // 2. 최신 날짜 기준: 통계 + 리버스카운트 + 랭킹 + 이전날짜를 한번에 병렬 조회
  const [statsRows, riverseCountRows, rankingRows, prevDateRows] = await Promise.all([
    sql`
      SELECT platform, COUNT(*)::int as total,
             COUNT(*) FILTER (WHERE is_riverse = TRUE)::int as riverse
      FROM rankings
      WHERE date = ${latestDate} AND COALESCE(sub_category, '') = ''
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

  // 3. 랭킹 변동 + 썸네일을 타이틀 기반으로 병렬 조회
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
          SELECT title, thumbnail_url
          FROM works
          WHERE platform = ${defaultPlatform}
            AND title = ANY(${titles})
            AND thumbnail_url IS NOT NULL
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
  for (const t of thumbRows) {
    if (t.thumbnail_url) thumbnails[t.title] = t.thumbnail_url;
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
  }));

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
