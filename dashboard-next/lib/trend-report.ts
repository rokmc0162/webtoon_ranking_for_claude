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

// ─── 공통 타입 ──────────────────────────────────

interface RankedWork {
  title: string;
  title_kr: string | null;
  platform: string;
  platform_name: string;
  rank: number;
  rank_change: number; // positive = improved
  unified_work_id: number | null;
  is_riverse: boolean;
}

interface RisingWork {
  title: string;
  title_kr: string | null;
  platform: string;
  platform_name: string;
  prev_rank: number;
  curr_rank: number;
  change: number;
  unified_work_id: number | null;
  is_riverse: boolean;
}

interface NewEntry {
  title: string;
  title_kr: string | null;
  platform: string;
  platform_name: string;
  rank: number;
  unified_work_id: number | null;
  is_riverse: boolean;
}

interface MultiPlatformWork {
  title: string;
  title_kr: string;
  platforms: { platform: string; platform_name: string; rank: number }[];
  platform_count: number;
  unified_work_id: number | null;
  is_riverse: boolean;
}

interface PlatformShare {
  platform: string;
  platform_name: string;
  total_ranked: number;
  riverse_count: number;
  share_pct: number;
}

// ─── 메인 TrendReport 타입 ──────────────────────────────────

export interface TrendReport {
  generated_at: string;
  data_date: string;
  prev_date: string;

  // 리버스 관점
  riverse: {
    summary: string;
    total_in_rankings: number;
    active_platforms: number;
    top_ranked: RankedWork[];       // TOP 리버스 작품 (최대 8)
    rising: RisingWork[];           // 급상승 리버스 (최대 5)
    new_entries: NewEntry[];        // 신규 진입 리버스 (최대 5)
    multi_platform: MultiPlatformWork[]; // 멀티플랫폼 리버스 (최대 5)
    platform_share: PlatformShare[];
  };

  // 타사(일본 시장) 관점
  market: {
    summary: string;
    top_rising: RisingWork[];       // 전체 시장 급상승 TOP (최대 8)
    new_entries: NewEntry[];        // 전체 시장 신규 TOP (최대 8)
    multi_platform: MultiPlatformWork[]; // 타사 멀티플랫폼 히트 (최대 5)
    top1_works: { title: string; title_kr: string | null; platform: string; platform_name: string; unified_work_id: number | null; is_riverse: boolean }[];
  };
}

// ─── 메인 생성 함수 ──────────────────────────────────

export async function generateTrendReport(): Promise<TrendReport | null> {
  try {
    const dateRows = await sql`
      SELECT DISTINCT date::text as date FROM rankings ORDER BY date DESC LIMIT 2
    `;
    if (dateRows.length < 2) return null;

    const dataDate = String(dateRows[0].date);
    const prevDate = String(dateRows[1].date);

    const [
      riverseTopRows,
      riverseSummaryRows,
      allRisingRows,
      allNewEntryRows,
      allMultiPlatformRows,
      shareRows,
      top1Rows,
    ] = await Promise.all([
      // 1) Riverse TOP ranked
      sql`
        SELECT r.title, COALESCE(r.title_kr, '') as title_kr, r.platform,
               r.rank::int as rank, r.is_riverse, w.unified_work_id,
               COALESCE(
                 (SELECT prev.rank::int FROM rankings prev
                  WHERE prev.date = ${prevDate} AND prev.platform = r.platform
                    AND prev.title = r.title AND COALESCE(prev.sub_category, '') = ''), 0
               ) as prev_rank
        FROM rankings r
        LEFT JOIN works w ON r.title = w.title AND r.platform = w.platform
        WHERE r.date = ${dataDate} AND COALESCE(r.sub_category, '') = ''
          AND r.is_riverse = TRUE
        ORDER BY r.rank ASC LIMIT 8
      `,

      // 2) Riverse count per platform
      sql`
        SELECT r.platform, COUNT(*)::int as cnt
        FROM rankings r
        WHERE r.date = ${dataDate} AND COALESCE(r.sub_category, '') = ''
          AND r.is_riverse = TRUE
        GROUP BY r.platform
      `,

      // 3) All rising works (both riverse and non-riverse)
      sql`
        SELECT curr.title, COALESCE(curr.title_kr, '') as title_kr, curr.platform,
               prev.rank::int as prev_rank, curr.rank::int as curr_rank,
               (prev.rank - curr.rank)::int as change,
               curr.is_riverse, w.unified_work_id
        FROM rankings curr
        INNER JOIN rankings prev
          ON prev.date = ${prevDate} AND prev.platform = curr.platform
          AND prev.title = curr.title AND COALESCE(prev.sub_category, '') = ''
        LEFT JOIN works w ON curr.title = w.title AND curr.platform = w.platform
        WHERE curr.date = ${dataDate} AND COALESCE(curr.sub_category, '') = ''
          AND (prev.rank - curr.rank) >= 5
        ORDER BY (prev.rank - curr.rank) DESC
        LIMIT 20
      `,

      // 4) All new entries (rank <= 30)
      sql`
        SELECT curr.title, COALESCE(curr.title_kr, '') as title_kr, curr.platform,
               curr.rank::int as rank, curr.is_riverse, w.unified_work_id
        FROM rankings curr
        LEFT JOIN works w ON curr.title = w.title AND curr.platform = w.platform
        WHERE curr.date = ${dataDate} AND COALESCE(curr.sub_category, '') = ''
          AND curr.rank <= 30
          AND NOT EXISTS (
            SELECT 1 FROM rankings prev
            WHERE prev.date = ${prevDate} AND prev.platform = curr.platform
              AND prev.title = curr.title AND COALESCE(prev.sub_category, '') = ''
          )
        ORDER BY curr.rank ASC LIMIT 16
      `,

      // 5) Multi-platform (3+ platforms)
      sql`
        SELECT uw.title_kr, uw.id as unified_work_id, uw.is_riverse,
               (array_agg(r.title ORDER BY r.rank))[1] as rep_title,
               json_agg(json_build_object('platform', r.platform, 'rank', r.rank::int) ORDER BY r.rank) as platforms
        FROM rankings r
        INNER JOIN works w ON r.title = w.title AND r.platform = w.platform
        INNER JOIN unified_works uw ON w.unified_work_id = uw.id
        WHERE r.date = ${dataDate} AND COALESCE(r.sub_category, '') = ''
          AND w.unified_work_id IS NOT NULL
        GROUP BY uw.id, uw.title_kr, uw.is_riverse
        HAVING COUNT(DISTINCT r.platform) >= 3
        ORDER BY COUNT(DISTINCT r.platform) DESC, MIN(r.rank) ASC
        LIMIT 12
      `,

      // 6) Platform riverse share
      sql`
        SELECT r.platform, COUNT(*)::int as total_ranked,
               COUNT(*) FILTER (WHERE r.is_riverse = TRUE)::int as riverse_count
        FROM rankings r
        WHERE r.date = ${dataDate} AND COALESCE(r.sub_category, '') = ''
        GROUP BY r.platform
        ORDER BY COUNT(*) FILTER (WHERE r.is_riverse = TRUE) DESC
      `,

      // 7) 각 플랫폼 1위 작품
      sql`
        SELECT r.title, COALESCE(r.title_kr, '') as title_kr, r.platform,
               r.is_riverse, w.unified_work_id
        FROM rankings r
        LEFT JOIN works w ON r.title = w.title AND r.platform = w.platform
        WHERE r.date = ${dataDate} AND COALESCE(r.sub_category, '') = ''
          AND r.rank = 1
      `,
    ]);

    // ── 데이터 가공 ──

    let totalRiverseInRankings = 0;
    let activePlatforms = 0;
    for (const row of riverseSummaryRows) {
      totalRiverseInRankings += row.cnt;
      activePlatforms++;
    }

    const topRiverse: RankedWork[] = riverseTopRows.map((r) => ({
      title: r.title, title_kr: r.title_kr || null,
      platform: r.platform, platform_name: platformName(r.platform),
      rank: r.rank, rank_change: r.prev_rank > 0 ? r.prev_rank - r.rank : 0,
      unified_work_id: r.unified_work_id ?? null, is_riverse: true,
    }));

    const allRising: RisingWork[] = allRisingRows.map((r) => ({
      title: r.title, title_kr: r.title_kr || null,
      platform: r.platform, platform_name: platformName(r.platform),
      prev_rank: r.prev_rank, curr_rank: r.curr_rank, change: r.change,
      unified_work_id: r.unified_work_id ?? null, is_riverse: !!r.is_riverse,
    }));

    const allNewEntries: NewEntry[] = allNewEntryRows.map((r) => ({
      title: r.title, title_kr: r.title_kr || null,
      platform: r.platform, platform_name: platformName(r.platform),
      rank: r.rank, unified_work_id: r.unified_work_id ?? null, is_riverse: !!r.is_riverse,
    }));

    const allMulti: MultiPlatformWork[] = allMultiPlatformRows.map((r) => {
      const platforms = (typeof r.platforms === "string" ? JSON.parse(r.platforms) : r.platforms) as { platform: string; rank: number }[];
      return {
        title: r.rep_title || r.title_kr,
        title_kr: r.title_kr,
        platforms: platforms.map((p) => ({ platform: p.platform, platform_name: platformName(p.platform), rank: p.rank })),
        platform_count: platforms.length,
        unified_work_id: r.unified_work_id ?? null,
        is_riverse: !!r.is_riverse,
      };
    });

    const platformShare: PlatformShare[] = shareRows.map((r) => ({
      platform: r.platform, platform_name: platformName(r.platform),
      total_ranked: r.total_ranked, riverse_count: r.riverse_count,
      share_pct: r.total_ranked > 0 ? Math.round((r.riverse_count / r.total_ranked) * 100) : 0,
    }));

    const top1Works = top1Rows.map((r) => ({
      title: r.title, title_kr: r.title_kr || null,
      platform: r.platform, platform_name: platformName(r.platform),
      unified_work_id: r.unified_work_id ?? null, is_riverse: !!r.is_riverse,
    }));

    // ── 리버스 / 타사 분리 ──

    const riverseRising = allRising.filter((w) => w.is_riverse).slice(0, 5);
    const riverseNew = allNewEntries.filter((w) => w.is_riverse).slice(0, 5);
    const riverseMulti = allMulti.filter((w) => w.is_riverse).slice(0, 5);

    const marketRising = allRising.slice(0, 8);
    const marketNew = allNewEntries.slice(0, 8);
    const marketMulti = allMulti.filter((w) => !w.is_riverse).slice(0, 5);

    // ── 요약문 생성 ──

    const riverseSummaryText = buildRiverseSummary({
      totalInRankings: totalRiverseInRankings,
      activePlatforms,
      topRanked: topRiverse,
      rising: riverseRising,
      platformShare,
    });

    const marketSummaryText = buildMarketSummary({
      rising: marketRising,
      newEntries: marketNew,
      multiPlatform: marketMulti,
      top1Works,
    });

    return {
      generated_at: new Date().toISOString(),
      data_date: dataDate,
      prev_date: prevDate,
      riverse: {
        summary: riverseSummaryText,
        total_in_rankings: totalRiverseInRankings,
        active_platforms: activePlatforms,
        top_ranked: topRiverse,
        rising: riverseRising,
        new_entries: riverseNew,
        multi_platform: riverseMulti,
        platform_share: platformShare,
      },
      market: {
        summary: marketSummaryText,
        top_rising: marketRising,
        new_entries: marketNew,
        multi_platform: marketMulti,
        top1_works: top1Works,
      },
    };
  } catch (e) {
    console.error("[TrendReport] Failed to generate:", e);
    return null;
  }
}

// ─── 한국어 조사 헬퍼 ──────────────────────────────────

function josa(word: string, withBatchim: string, withoutBatchim: string): string {
  if (!word) return withBatchim;
  const lastChar = word[word.length - 1];
  const code = lastChar.charCodeAt(0);
  if (code >= 0xAC00 && code <= 0xD7A3) {
    return (code - 0xAC00) % 28 !== 0 ? withBatchim : withoutBatchim;
  }
  if (/[0-9]$/.test(lastChar)) return "01367".includes(lastChar) ? withBatchim : withoutBatchim;
  if (/[a-zA-Z]$/.test(lastChar)) return /[lmnrptLMNRPT]$/.test(lastChar) ? withBatchim : withoutBatchim;
  return withBatchim;
}

// ─── 리버스 요약문 (한 줄 한 문장, 개행 구분) ──────────────────

function buildRiverseSummary(d: {
  totalInRankings: number;
  activePlatforms: number;
  topRanked: RankedWork[];
  rising: RisingWork[];
  platformShare: PlatformShare[];
}): string {
  const lines: string[] = [];

  // 총 현황
  lines.push(`${d.activePlatforms}개 플랫폼, ${d.totalInRankings}건 랭킹 진입`);

  // 최고 순위
  if (d.topRanked.length > 0) {
    const t = d.topRanked[0];
    if (t.rank <= 3) {
      lines.push(`${t.platform_name} ${t.rank}위 «${t.title}» — 선두 유지`);
    } else {
      lines.push(`최고 순위: ${t.platform_name} ${t.rank}위 «${t.title}»`);
    }
  }

  // 점유율
  const activeShares = d.platformShare.filter((p) => p.riverse_count > 0);
  if (activeShares.length > 0) {
    const top = activeShares.reduce((a, b) => (a.share_pct > b.share_pct ? a : b));
    if (top.share_pct >= 3) {
      lines.push(`${top.platform_name} 점유율 ${top.share_pct}% 최고`);
    }
  }

  // 급상승
  if (d.rising.length > 0) {
    const r = d.rising[0];
    lines.push(`급상승 «${r.title}» ${r.prev_rank}→${r.curr_rank}위 (+${r.change})`);
  }

  return lines.join("\n");
}

// ─── 시장 전체 요약문 (한 줄 한 문장, 개행 구분) ──────────────────

function buildMarketSummary(d: {
  rising: RisingWork[];
  newEntries: NewEntry[];
  multiPlatform: MultiPlatformWork[];
  top1Works: { title: string; title_kr: string | null; platform: string; platform_name: string; is_riverse: boolean }[];
}): string {
  const lines: string[] = [];

  // 급상승
  if (d.rising.length > 0) {
    const r = d.rising[0];
    lines.push(`최대 급상승 «${r.title}» +${r.change}계단 (${r.platform_name})`);
    if (d.rising.length > 2) {
      lines.push(`5위 이상 상승 ${d.rising.length}작품`);
    }
  }

  // 신규 진입
  if (d.newEntries.length > 0) {
    const top = d.newEntries.filter((w) => w.rank <= 3);
    if (top.length > 0) {
      const w = top[0];
      lines.push(`신규 주목 «${w.title}» ${w.platform_name} ${w.rank}위 진입`);
    }
    lines.push(`TOP 30 신규 ${d.newEntries.length}작품`);
  }

  // 멀티플랫폼
  if (d.multiPlatform.length > 0) {
    const m = d.multiPlatform[0];
    lines.push(`«${m.title}» ${m.platform_count}개 플랫폼 동시 랭크인`);
  }

  return lines.join("\n");
}
