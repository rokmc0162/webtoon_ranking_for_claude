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

// ─── 리버스 요약문 ──────────────────────────────────

function buildRiverseSummary(d: {
  totalInRankings: number;
  activePlatforms: number;
  topRanked: RankedWork[];
  rising: RisingWork[];
  platformShare: PlatformShare[];
}): string {
  const parts: string[] = [];

  if (d.topRanked.length > 0) {
    const top1 = d.topRanked[0];
    const activeShares = d.platformShare.filter((p) => p.riverse_count > 0);
    const topShare = activeShares.length > 0
      ? activeShares.reduce((a, b) => (a.share_pct > b.share_pct ? a : b))
      : null;

    let text = `${d.activePlatforms}개 플랫폼에서 총 ${d.totalInRankings}건 랭킹 진입.`;
    if (top1.rank <= 3) {
      text += ` «${top1.title_kr || top1.title}»${josa(top1.title_kr || top1.title, "이", "가")} ${top1.platform_name} ${top1.rank}위로 선두를 유지하고 있습니다.`;
    } else {
      text += ` 최고 순위 ${top1.platform_name} «${top1.title_kr || top1.title}» ${top1.rank}위.`;
    }
    if (topShare && topShare.share_pct >= 3) {
      text += ` ${topShare.platform_name} 점유율 ${topShare.share_pct}%로 최고.`;
    }
    parts.push(text);
  }

  if (d.rising.length > 0) {
    const top = d.rising[0];
    const topName = top.title_kr || top.title;
    parts.push(`급상승: «${topName}» ${top.prev_rank}→${top.curr_rank}위(+${top.change}, ${top.platform_name})${d.rising.length > 1 ? ` 외 ${d.rising.length - 1}작` : ""}`);
  }

  return parts.join(" ");
}

// ─── 시장 전체 요약문 ──────────────────────────────────

function buildMarketSummary(d: {
  rising: RisingWork[];
  newEntries: NewEntry[];
  multiPlatform: MultiPlatformWork[];
  top1Works: { title: string; title_kr: string | null; platform: string; platform_name: string; is_riverse: boolean }[];
}): string {
  const parts: string[] = [];

  // 각 플랫폼 1위 중 눈에 띄는 변화
  const nonRiverseTop1 = d.top1Works.filter((w) => !w.is_riverse);
  if (nonRiverseTop1.length > 0) {
    const examples = nonRiverseTop1.slice(0, 3).map((w) => `${w.platform_name} «${w.title_kr || w.title}»`);
    parts.push(`각 플랫폼 1위: ${examples.join(", ")}${nonRiverseTop1.length > 3 ? " 등" : ""}.`);
  }

  if (d.rising.length > 0) {
    const top = d.rising[0];
    const topName = top.title_kr || top.title;
    parts.push(`최대 급상승: «${topName}» ${top.prev_rank}→${top.curr_rank}위(+${top.change}, ${top.platform_name}).${d.rising.length > 2 ? ` 총 ${d.rising.length}작품이 5위 이상 상승.` : ""}`);
  }

  if (d.newEntries.length > 0) {
    const top1New = d.newEntries.filter((w) => w.rank <= 3);
    if (top1New.length > 0) {
      const names = top1New.slice(0, 2).map((w) => `«${w.title_kr || w.title}»(${w.platform_name} ${w.rank}위)`);
      parts.push(`주목 신규: ${names.join(", ")} 등 ${d.newEntries.length}작품 TOP 30 진입.`);
    } else {
      parts.push(`신규 ${d.newEntries.length}작품이 TOP 30에 진입.`);
    }
  }

  if (d.multiPlatform.length > 0) {
    const top = d.multiPlatform[0];
    parts.push(`크로스플랫폼: «${top.title_kr}» ${top.platform_count}개 플랫폼 동시 랭크인${d.multiPlatform.length > 1 ? ` 외 ${d.multiPlatform.length - 1}작` : ""}.`);
  }

  return parts.join(" ");
}
