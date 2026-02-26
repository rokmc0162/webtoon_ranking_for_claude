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

  /** 사람이 읽는 해석적 요약문 (서버사이드 JS 로직으로 자동 생성) */
  summary: string;

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

    // 해석적 요약문 생성 (순수 JS 로직, AI 토큰 불사용)
    const summary = buildNarrativeSummary({
      dataDate,
      totalPlatforms,
      totalRiverseInRankings,
      topRiverse,
      risingWorks,
      newEntries,
      multiPlatform,
      platformRiverseShare,
    });

    return {
      generated_at: new Date().toISOString(),
      data_date: dataDate,
      prev_date: prevDate,
      summary,
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

// ─── 해석적 요약문 생성 로직 ──────────────────────────────────

interface SummaryInput {
  dataDate: string;
  totalPlatforms: number;
  totalRiverseInRankings: number;
  topRiverse: TrendReport["riverse_summary"]["top_riverse"];
  risingWorks: TrendReport["rising_works"];
  newEntries: TrendReport["new_entries"];
  multiPlatform: TrendReport["multi_platform"];
  platformRiverseShare: TrendReport["platform_riverse_share"];
}

function buildNarrativeSummary(d: SummaryInput): string {
  const parts: string[] = [];

  // ── 1. 리버스 현황 총평 ──
  const activePlatforms = d.platformRiverseShare.filter((p) => p.riverse_count > 0);
  const topSharePlatform = activePlatforms.length > 0
    ? activePlatforms.reduce((a, b) => (a.share_pct > b.share_pct ? a : b))
    : null;

  if (d.topRiverse.length > 0) {
    const top1 = d.topRiverse[0];
    const top3Names = d.topRiverse
      .slice(0, 3)
      .map((w) => w.title_kr)
      .join(", ");

    let opener = `${d.totalPlatforms}개 플랫폼에서 리버스 작품 총 ${d.totalRiverseInRankings}건이 종합 랭킹에 진입해 있습니다.`;
    if (top1.rank <= 3) {
      opener += ` 특히 «${top1.title_kr}»이(가) ${top1.platform_name} ${top1.rank}위를 기록하며 상위권을 유지하고 있습니다.`;
    } else {
      opener += ` 최고 순위는 ${top1.platform_name}의 «${top1.title_kr}» ${top1.rank}위입니다.`;
    }

    // 리버스 점유율 언급
    if (topSharePlatform && topSharePlatform.share_pct >= 5) {
      opener += ` 점유율은 ${topSharePlatform.platform_name}이(가) ${topSharePlatform.share_pct}%로 가장 높습니다.`;
    }

    parts.push(opener);
  } else {
    parts.push(`현재 ${d.totalPlatforms}개 플랫폼 종합 랭킹에 리버스 작품 ${d.totalRiverseInRankings}건이 등록되어 있습니다.`);
  }

  // ── 2. 급상승 동향 ──
  if (d.risingWorks.length > 0) {
    const top = d.risingWorks[0];
    const topName = top.title_kr || top.title;
    let risingText = `전일 대비 가장 큰 상승세를 보인 작품은 «${topName}»으로, ${top.platform_name}에서 ${top.prev_rank}위→${top.curr_rank}위(+${top.change})를 기록했습니다.`;

    if (d.risingWorks.length > 1) {
      const second = d.risingWorks[1];
      const secondName = second.title_kr || second.title;
      risingText += ` «${secondName}»(+${second.change}) 등 총 ${d.risingWorks.length}작품이 5위 이상 급상승했습니다.`;
    }

    // 리버스 급상승 있는지 체크
    const riverseRising = d.risingWorks.filter((w) => {
      return d.topRiverse.some((r) => r.title_kr === (w.title_kr || w.title));
    });
    if (riverseRising.length > 0) {
      const rr = riverseRising[0];
      risingText += ` 이 중 리버스 작품 «${rr.title_kr || rr.title}»도 +${rr.change}으로 주목할 만합니다.`;
    }

    parts.push(risingText);
  }

  // ── 3. 신규 진입 ──
  if (d.newEntries.length > 0) {
    const top1Entries = d.newEntries.filter((w) => w.rank === 1);
    if (top1Entries.length > 0) {
      const names = top1Entries
        .map((w) => `«${w.title_kr || w.title}»(${w.platform_name})`)
        .join(", ");
      parts.push(
        `신규 진입 중 ${names}이(가) 1위에 바로 올라 눈에 띕니다. 총 ${d.newEntries.length}작품이 TOP 30에 새로 등장했습니다.`
      );
    } else {
      const topEntry = d.newEntries[0];
      parts.push(
        `신규 작품 ${d.newEntries.length}건이 TOP 30에 진입했으며, «${topEntry.title_kr || topEntry.title}»이(가) ${topEntry.platform_name} ${topEntry.rank}위로 가장 높은 순위를 기록했습니다.`
      );
    }
  }

  // ── 4. 멀티플랫폼 인기작 ──
  if (d.multiPlatform.length > 0) {
    const top = d.multiPlatform[0];
    let multiText = `«${top.title_kr}»이(가) ${top.platform_count}개 플랫폼에서 동시 랭크인하며 크로스플랫폼 인기를 입증하고 있습니다.`;
    if (d.multiPlatform.length > 2) {
      multiText += ` 외 ${d.multiPlatform.length - 1}작품이 3개 이상 플랫폼에 동시 노출 중입니다.`;
    }
    parts.push(multiText);
  }

  return parts.join("\n\n");
}
