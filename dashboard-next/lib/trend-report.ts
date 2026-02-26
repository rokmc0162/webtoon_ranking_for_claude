import { sql } from "@/lib/supabase";

const PLATFORM_NAMES: Record<string, string> = {
  piccoma: "픽코마",
  linemanga: "라인망가",
  mechacomic: "메챠코믹",
  cmoa: "코믹시모아",
  comico: "코미코",
  renta: "렌타",
  booklive: "북라이브",
  ebookjapan: "이북재팬",
  lezhin: "레진코믹스",
  beltoon: "벨툰",
  unext: "U-NEXT",
  asura: "Asura Scans",
};

function platformName(id: string): string {
  return PLATFORM_NAMES[id] ?? id;
}

export interface TrendReport {
  generated_at: string;
  data_date: string;
  prev_date: string;

  riverse_summary: {
    total_platforms: number;
    total_riverse_in_rankings: number;
    top_riverse: {
      title_kr: string;
      platform: string;
      platform_name: string;
      rank: number;
      rank_change: number;
      unified_work_id: number | null;
    }[];
  };

  rising_works: {
    title: string;
    title_kr: string | null;
    platform: string;
    platform_name: string;
    prev_rank: number;
    curr_rank: number;
    change: number;
    unified_work_id: number | null;
  }[];

  new_entries: {
    title: string;
    title_kr: string | null;
    platform: string;
    platform_name: string;
    rank: number;
    unified_work_id: number | null;
  }[];

  multi_platform: {
    title_kr: string;
    platforms: { platform: string; platform_name: string; rank: number }[];
    platform_count: number;
    unified_work_id: number | null;
  }[];

  platform_riverse_share: {
    platform: string;
    platform_name: string;
    total_ranked: number;
    riverse_count: number;
    share_pct: number;
  }[];
}

export async function generateTrendReport(): Promise<TrendReport | null> {
  try {
    // 1. Get the latest 2 dates from rankings
    const dateRows = await sql`
      SELECT DISTINCT date::text as date
      FROM rankings
      ORDER BY date DESC
      LIMIT 2
    `;

    if (dateRows.length < 2) return null;

    const dataDate = String(dateRows[0].date);
    const prevDate = String(dateRows[1].date);

    // 2. Run all queries in parallel
    const [
      riverseTopRows,
      riverseSummaryRows,
      risingRows,
      newEntryRows,
      multiPlatformRows,
      shareRows,
    ] = await Promise.all([
      // Top riverse works in today's overall rankings
      sql`
        SELECT
          r.title,
          COALESCE(r.title_kr, '') as title_kr,
          r.platform,
          r.rank::int as rank,
          w.unified_work_id,
          COALESCE(
            (SELECT prev.rank::int FROM rankings prev
             WHERE prev.date = ${prevDate}
               AND prev.platform = r.platform
               AND prev.title = r.title
               AND COALESCE(prev.sub_category, '') = ''),
            0
          ) as prev_rank
        FROM rankings r
        LEFT JOIN works w ON r.title = w.title AND r.platform = w.platform
        WHERE r.date = ${dataDate}
          AND COALESCE(r.sub_category, '') = ''
          AND r.is_riverse = TRUE
        ORDER BY r.rank ASC
        LIMIT 10
      `,

      // Riverse summary: count per platform + total
      sql`
        SELECT
          r.platform,
          COUNT(*)::int as cnt
        FROM rankings r
        WHERE r.date = ${dataDate}
          AND COALESCE(r.sub_category, '') = ''
          AND r.is_riverse = TRUE
        GROUP BY r.platform
      `,

      // Rising works: biggest rank improvements (min change 5)
      sql`
        SELECT
          curr.title,
          COALESCE(curr.title_kr, '') as title_kr,
          curr.platform,
          prev.rank::int as prev_rank,
          curr.rank::int as curr_rank,
          (prev.rank - curr.rank)::int as change,
          w.unified_work_id
        FROM rankings curr
        INNER JOIN rankings prev
          ON prev.date = ${prevDate}
          AND prev.platform = curr.platform
          AND prev.title = curr.title
          AND COALESCE(prev.sub_category, '') = ''
        LEFT JOIN works w ON curr.title = w.title AND curr.platform = w.platform
        WHERE curr.date = ${dataDate}
          AND COALESCE(curr.sub_category, '') = ''
          AND (prev.rank - curr.rank) >= 5
        ORDER BY (prev.rank - curr.rank) DESC
        LIMIT 8
      `,

      // New entries: in today's rankings but not in yesterday's, rank <= 30
      sql`
        SELECT
          curr.title,
          COALESCE(curr.title_kr, '') as title_kr,
          curr.platform,
          curr.rank::int as rank,
          w.unified_work_id
        FROM rankings curr
        LEFT JOIN works w ON curr.title = w.title AND curr.platform = w.platform
        WHERE curr.date = ${dataDate}
          AND COALESCE(curr.sub_category, '') = ''
          AND curr.rank <= 30
          AND NOT EXISTS (
            SELECT 1 FROM rankings prev
            WHERE prev.date = ${prevDate}
              AND prev.platform = curr.platform
              AND prev.title = curr.title
              AND COALESCE(prev.sub_category, '') = ''
          )
        ORDER BY curr.rank ASC
        LIMIT 8
      `,

      // Multi-platform hits: unified_work_id appearing in 3+ platforms
      sql`
        SELECT
          uw.title_kr,
          uw.id as unified_work_id,
          json_agg(
            json_build_object(
              'platform', r.platform,
              'rank', r.rank::int
            ) ORDER BY r.rank
          ) as platforms
        FROM rankings r
        INNER JOIN works w ON r.title = w.title AND r.platform = w.platform
        INNER JOIN unified_works uw ON w.unified_work_id = uw.id
        WHERE r.date = ${dataDate}
          AND COALESCE(r.sub_category, '') = ''
          AND w.unified_work_id IS NOT NULL
        GROUP BY uw.id, uw.title_kr
        HAVING COUNT(DISTINCT r.platform) >= 3
        ORDER BY COUNT(DISTINCT r.platform) DESC, MIN(r.rank) ASC
        LIMIT 8
      `,

      // Platform riverse share
      sql`
        SELECT
          r.platform,
          COUNT(*)::int as total_ranked,
          COUNT(*) FILTER (WHERE r.is_riverse = TRUE)::int as riverse_count
        FROM rankings r
        WHERE r.date = ${dataDate}
          AND COALESCE(r.sub_category, '') = ''
        GROUP BY r.platform
        ORDER BY COUNT(*) FILTER (WHERE r.is_riverse = TRUE) DESC
      `,
    ]);

    // Process riverse summary
    let totalRiverseInRankings = 0;
    let totalPlatforms = 0;
    for (const row of riverseSummaryRows) {
      totalRiverseInRankings += row.cnt;
      totalPlatforms++;
    }

    const topRiverse = riverseTopRows.map((r) => ({
      title_kr: r.title_kr || r.title,
      platform: r.platform,
      platform_name: platformName(r.platform),
      rank: r.rank,
      rank_change: r.prev_rank > 0 ? r.prev_rank - r.rank : 0,
      unified_work_id: r.unified_work_id ?? null,
    }));

    // Process rising works
    const risingWorks = risingRows.map((r) => ({
      title: r.title,
      title_kr: r.title_kr || null,
      platform: r.platform,
      platform_name: platformName(r.platform),
      prev_rank: r.prev_rank,
      curr_rank: r.curr_rank,
      change: r.change,
      unified_work_id: r.unified_work_id ?? null,
    }));

    // Process new entries
    const newEntries = newEntryRows.map((r) => ({
      title: r.title,
      title_kr: r.title_kr || null,
      platform: r.platform,
      platform_name: platformName(r.platform),
      rank: r.rank,
      unified_work_id: r.unified_work_id ?? null,
    }));

    // Process multi-platform
    const multiPlatform = multiPlatformRows.map((r) => {
      const platforms = (
        typeof r.platforms === "string"
          ? JSON.parse(r.platforms)
          : r.platforms
      ) as { platform: string; rank: number }[];
      return {
        title_kr: r.title_kr,
        platforms: platforms.map((p) => ({
          platform: p.platform,
          platform_name: platformName(p.platform),
          rank: p.rank,
        })),
        platform_count: platforms.length,
        unified_work_id: r.unified_work_id ?? null,
      };
    });

    // Process platform share
    const platformRiverseShare = shareRows.map((r) => ({
      platform: r.platform,
      platform_name: platformName(r.platform),
      total_ranked: r.total_ranked,
      riverse_count: r.riverse_count,
      share_pct:
        r.total_ranked > 0
          ? Math.round((r.riverse_count / r.total_ranked) * 100)
          : 0,
    }));

    return {
      generated_at: new Date().toISOString(),
      data_date: dataDate,
      prev_date: prevDate,
      riverse_summary: {
        total_platforms: totalPlatforms,
        total_riverse_in_rankings: totalRiverseInRankings,
        top_riverse: topRiverse,
      },
      rising_works: risingWorks,
      new_entries: newEntries,
      multi_platform: multiPlatform,
      platform_riverse_share: platformRiverseShare,
    };
  } catch (e) {
    console.error("[TrendReport] Failed to generate:", e);
    return null;
  }
}
