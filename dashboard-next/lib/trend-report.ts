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

const PLATFORM_COLORS: Record<string, string> = {
  piccoma: "#F5C518",
  linemanga: "#06C755",
  mechacomic: "#E85298",
  cmoa: "#00A1E9",
  comico: "#FF6B35",
  renta: "#7B2D8B",
  booklive: "#FF7E00",
  ebookjapan: "#E4002B",
  lezhin: "#FF2A2A",
  beltoon: "#1DB954",
  unext: "#242424",
  asura: "#854DFF",
};

function platformName(id: string): string {
  return PLATFORM_NAMES[id] ?? id;
}

// ─── 공통 타입 ──────────────────────────────────

export interface SparklinePoint {
  date: string;
  rank: number | null;
}

interface RankedWork {
  title: string;
  title_kr: string | null;
  platform: string;
  platform_name: string;
  rank: number;
  rank_change: number;
  unified_work_id: number | null;
  is_riverse: boolean;
}

export interface RankedWorkWithSparkline extends RankedWork {
  sparkline: SparklinePoint[];
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

export interface FallingWork {
  title: string;
  title_kr: string | null;
  platform: string;
  platform_name: string;
  prev_rank: number;
  curr_rank: number;
  change: number; // positive = fell (e.g. 10→25 = change 15)
  unified_work_id: number | null;
  is_riverse: boolean;
}

export interface KpiMetrics {
  riverse_in_rankings: number;
  riverse_in_rankings_delta: number;
  riverse_avg_rank: number;
  riverse_avg_rank_delta: number; // negative = improved
  riverse_top3_count: number;
  riverse_top3_delta: number;
  riverse_share_pct: number;
  riverse_share_pct_delta: number;
}

export interface ConsistentPerformer {
  title: string;
  title_kr: string | null;
  platform: string;
  platform_name: string;
  unified_work_id: number | null;
  is_riverse: boolean;
  consecutive_days: number;
  current_rank: number;
  best_rank_in_period: number;
  sparkline: SparklinePoint[];
}

export interface GenreTrend {
  genre: string;
  genre_kr: string;
  current_count: number;
  prev_count: number;
  delta: number;
  riverse_count: number;
  top_work: {
    title: string;
    platform: string;
    rank: number;
    is_riverse: boolean;
    unified_work_id: number | null;
  } | null;
}

export interface PlatformComparison {
  platform: string;
  platform_name: string;
  platform_color: string;
  total_ranked: number;
  riverse_count: number;
  share_pct: number;
  avg_riverse_rank: number | null;
}

// ─── 메인 TrendReport 타입 ──────────────────────────────────

export interface TrendReport {
  generated_at: string;
  data_date: string;
  prev_date: string;
  date_7d_ago: string;

  kpi: KpiMetrics;

  riverse: {
    summary: string;
    total_in_rankings: number;
    active_platforms: number;
    top_ranked: RankedWorkWithSparkline[];
    rising: RisingWork[];
    falling: FallingWork[];
    new_entries: NewEntry[];
    multi_platform: MultiPlatformWork[];
    platform_share: PlatformShare[];
    consistent_performers: ConsistentPerformer[];
  };

  market: {
    summary: string;
    top_rising: RisingWork[];
    top_falling: FallingWork[];
    new_entries: NewEntry[];
    multi_platform: MultiPlatformWork[];
    top1_works: { title: string; title_kr: string | null; platform: string; platform_name: string; unified_work_id: number | null; is_riverse: boolean }[];
  };

  genre_trends: GenreTrend[];
  platform_comparison: PlatformComparison[];
}

// ─── 메인 생성 함수 ──────────────────────────────────

export async function generateTrendReport(): Promise<TrendReport | null> {
  try {
    // 날짜 범위: 최근 8일치
    const dateRows = await sql`
      SELECT DISTINCT date::text as date FROM rankings ORDER BY date DESC LIMIT 8
    `;
    if (dateRows.length < 2) return null;

    const allDates = dateRows.map((r) => String(r.date));
    const dataDate = allDates[0];
    const prevDate = allDates[1];
    const date7dAgo = allDates[allDates.length - 1]; // 가용한 가장 오래된 날짜

    const [
      // 기존 7개
      riverseTopRows,
      riverseSummaryRows,
      allRisingRows,
      allNewEntryRows,
      allMultiPlatformRows,
      shareRows,
      top1Rows,
      // 신규 6개
      kpi7dRows,
      allFallingRows,
      consistentRows,
      genreCurrRows,
      genre7dRows,
      platformCompRows,
    ] = await Promise.all([
      // ===== 기존 쿼리 (1~7) =====

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

      // 3) All rising works (>= 5 rank improvement)
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

      // 7) 각 플랫폼 1위
      sql`
        SELECT r.title, COALESCE(r.title_kr, '') as title_kr, r.platform,
               r.is_riverse, w.unified_work_id
        FROM rankings r
        LEFT JOIN works w ON r.title = w.title AND r.platform = w.platform
        WHERE r.date = ${dataDate} AND COALESCE(r.sub_category, '') = ''
          AND r.rank = 1
      `,

      // ===== 신규 쿼리 (8~13) =====

      // 8) KPI: 7일전 리버스 통계
      sql`
        SELECT
          COUNT(*) FILTER (WHERE is_riverse = TRUE)::int as rv_count,
          ROUND(AVG(rank) FILTER (WHERE is_riverse = TRUE))::int as rv_avg_rank,
          COUNT(*) FILTER (WHERE is_riverse = TRUE AND rank <= 3)::int as rv_top3,
          COUNT(*)::int as total,
          COUNT(*) FILTER (WHERE is_riverse = TRUE)::int as rv_total
        FROM rankings
        WHERE date = ${date7dAgo} AND COALESCE(sub_category, '') = ''
      `,

      // 9) 하락 작품 (5위 이상 하락)
      sql`
        SELECT curr.title, COALESCE(curr.title_kr, '') as title_kr, curr.platform,
               prev.rank::int as prev_rank, curr.rank::int as curr_rank,
               (curr.rank - prev.rank)::int as change,
               curr.is_riverse, w.unified_work_id
        FROM rankings curr
        INNER JOIN rankings prev
          ON prev.date = ${prevDate} AND prev.platform = curr.platform
          AND prev.title = curr.title AND COALESCE(prev.sub_category, '') = ''
        LEFT JOIN works w ON curr.title = w.title AND curr.platform = w.platform
        WHERE curr.date = ${dataDate} AND COALESCE(curr.sub_category, '') = ''
          AND (curr.rank - prev.rank) >= 5
        ORDER BY (curr.rank - prev.rank) DESC
        LIMIT 10
      `,

      // 10) 안정 인기작 (최근 N일 중 3일+ TOP 10)
      sql`
        WITH recent_top AS (
          SELECT r.title, r.platform, r.date::text as date, r.rank::int as rank,
                 r.is_riverse, COALESCE(r.title_kr, '') as title_kr, w.unified_work_id
          FROM rankings r
          LEFT JOIN works w ON r.title = w.title AND r.platform = w.platform
          WHERE r.date = ANY(${allDates})
            AND COALESCE(r.sub_category, '') = '' AND r.rank <= 10
        )
        SELECT title, platform, title_kr, is_riverse, unified_work_id,
               COUNT(DISTINCT date)::int as consecutive_days,
               MIN(rank)::int as best_rank_in_period
        FROM recent_top
        GROUP BY title, platform, title_kr, is_riverse, unified_work_id
        HAVING COUNT(DISTINCT date) >= 3
        ORDER BY COUNT(DISTINCT date) DESC, MIN(rank) ASC
        LIMIT 10
      `,

      // 11) 장르 현재 분포
      sql`
        SELECT COALESCE(w.genre_kr, '') as genre_kr, COALESCE(w.genre, '') as genre,
               COUNT(*)::int as cnt,
               COUNT(*) FILTER (WHERE r.is_riverse = TRUE)::int as rv_cnt,
               MIN(r.rank)::int as best_rank,
               (array_agg(r.title ORDER BY r.rank))[1] as top_title,
               (array_agg(r.platform ORDER BY r.rank))[1] as top_platform,
               (array_agg(r.is_riverse ORDER BY r.rank))[1] as top_is_rv,
               (array_agg(w.unified_work_id ORDER BY r.rank))[1] as top_uwid
        FROM rankings r
        LEFT JOIN works w ON r.title = w.title AND r.platform = w.platform
        WHERE r.date = ${dataDate} AND COALESCE(r.sub_category, '') = ''
          AND COALESCE(w.genre_kr, '') != ''
        GROUP BY COALESCE(w.genre_kr, ''), COALESCE(w.genre, '')
        ORDER BY COUNT(*) DESC
        LIMIT 15
      `,

      // 12) 장르 7일전 분포 (비교용)
      sql`
        SELECT COALESCE(w.genre_kr, '') as genre_kr, COUNT(*)::int as cnt
        FROM rankings r
        LEFT JOIN works w ON r.title = w.title AND r.platform = w.platform
        WHERE r.date = ${date7dAgo} AND COALESCE(r.sub_category, '') = ''
          AND COALESCE(w.genre_kr, '') != ''
        GROUP BY COALESCE(w.genre_kr, '')
      `,

      // 13) 플랫폼 비교 상세
      sql`
        SELECT r.platform,
          COUNT(*)::int as total_ranked,
          COUNT(*) FILTER (WHERE r.is_riverse = TRUE)::int as riverse_count,
          ROUND(AVG(r.rank) FILTER (WHERE r.is_riverse = TRUE))::int as avg_rv_rank
        FROM rankings r
        WHERE r.date = ${dataDate} AND COALESCE(r.sub_category, '') = ''
        GROUP BY r.platform
        ORDER BY COUNT(*) FILTER (WHERE r.is_riverse = TRUE) DESC
      `,
    ]);

    // ── 기존 데이터 가공 ──

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

    // ── 신규 데이터 가공 ──

    // KPI 계산
    const currTotal = shareRows.reduce((s, r) => s + r.total_ranked, 0);
    const currRvTotal = shareRows.reduce((s, r) => s + r.riverse_count, 0);
    const currRvAvg = topRiverse.length > 0
      ? Math.round(topRiverse.reduce((s, w) => s + w.rank, 0) / topRiverse.length)
      : 0;
    // 현재 TOP3 수 계산: 전체 리버스 랭킹에서 rank <= 3
    const currTop3 = riverseTopRows.filter((r) => r.rank <= 3).length;
    const currSharePct = currTotal > 0 ? Math.round((currRvTotal / currTotal) * 100 * 10) / 10 : 0;

    // 현재 리버스 평균 순위 (모든 리버스 작품 대상)
    // 좀 더 정확한 평균을 위해 shareRows의 riverse_count와 KPI 7d 데이터 활용
    const kpi7d = kpi7dRows[0] || { rv_count: 0, rv_avg_rank: 0, rv_top3: 0, total: 0, rv_total: 0 };
    const prev7dSharePct = kpi7d.total > 0 ? Math.round((kpi7d.rv_total / kpi7d.total) * 100 * 10) / 10 : 0;

    // 현재 리버스 평균순위 계산 (전체 플랫폼 대상)
    const avgRankRows = await sql`
      SELECT ROUND(AVG(rank))::int as avg_rank
      FROM rankings
      WHERE date = ${dataDate} AND COALESCE(sub_category, '') = '' AND is_riverse = TRUE
    `;
    const currRvAvgAll = avgRankRows[0]?.avg_rank ?? 0;

    const kpi: KpiMetrics = {
      riverse_in_rankings: currRvTotal,
      riverse_in_rankings_delta: currRvTotal - (kpi7d.rv_count || 0),
      riverse_avg_rank: currRvAvgAll,
      riverse_avg_rank_delta: currRvAvgAll - (kpi7d.rv_avg_rank || 0),
      riverse_top3_count: currTop3,
      riverse_top3_delta: currTop3 - (kpi7d.rv_top3 || 0),
      riverse_share_pct: currSharePct,
      riverse_share_pct_delta: Math.round((currSharePct - prev7dSharePct) * 10) / 10,
    };

    // 하락 작품
    const allFalling: FallingWork[] = allFallingRows.map((r) => ({
      title: r.title, title_kr: r.title_kr || null,
      platform: r.platform, platform_name: platformName(r.platform),
      prev_rank: r.prev_rank, curr_rank: r.curr_rank, change: r.change,
      unified_work_id: r.unified_work_id ?? null, is_riverse: !!r.is_riverse,
    }));

    // 안정 인기작 (스파크라인은 2차 쿼리)
    const consistentBase = consistentRows.map((r) => ({
      title: String(r.title),
      title_kr: r.title_kr || null,
      platform: String(r.platform),
      platform_name: platformName(String(r.platform)),
      unified_work_id: r.unified_work_id ?? null,
      is_riverse: !!r.is_riverse,
      consecutive_days: Number(r.consecutive_days),
      current_rank: 0,
      best_rank_in_period: Number(r.best_rank_in_period),
      sparkline: [] as SparklinePoint[],
    }));

    // 안정 인기작 + TOP 리버스 스파크라인 데이터를 한번에 가져오기
    const sparklineTitles = [
      ...topRiverse.map((w) => ({ title: w.title, platform: w.platform })),
      ...consistentBase.map((w) => ({ title: w.title, platform: w.platform })),
    ];
    const uniqueSparkKeys = new Set<string>();
    const filteredSparkTitles = sparklineTitles.filter((w) => {
      const key = `${w.platform}:${w.title}`;
      if (uniqueSparkKeys.has(key)) return false;
      uniqueSparkKeys.add(key);
      return true;
    });

    let sparklineMap = new Map<string, SparklinePoint[]>();
    if (filteredSparkTitles.length > 0) {
      const sparkTitles = filteredSparkTitles.map((w) => w.title);
      const sparkPlatforms = filteredSparkTitles.map((w) => w.platform);
      const sparkRows = await sql`
        SELECT r.title, r.platform, r.date::text as date, r.rank::int as rank
        FROM rankings r
        WHERE r.date = ANY(${allDates})
          AND COALESCE(r.sub_category, '') = ''
          AND r.title = ANY(${sparkTitles})
          AND r.platform = ANY(${sparkPlatforms})
        ORDER BY r.date ASC
      `;
      for (const r of sparkRows) {
        const key = `${r.platform}:${r.title}`;
        if (!sparklineMap.has(key)) sparklineMap.set(key, []);
        // 중복 date 체크 (같은 title이 다른 platform의 sparkTitles에 포함될 수 있음)
        const existing = sparklineMap.get(key)!;
        if (!existing.find((p) => p.date === r.date)) {
          existing.push({ date: String(r.date), rank: r.rank });
        }
      }
    }

    // TOP 리버스에 스파크라인 연결
    const topRiverseWithSparkline: RankedWorkWithSparkline[] = topRiverse.map((w) => ({
      ...w,
      sparkline: sparklineMap.get(`${w.platform}:${w.title}`) || [],
    }));

    // 안정 인기작에 현재 순위 + 스파크라인 연결
    const consistentPerformers: ConsistentPerformer[] = consistentBase.map((w) => {
      const sp = sparklineMap.get(`${w.platform}:${w.title}`) || [];
      const lastPoint = sp.length > 0 ? sp[sp.length - 1] : null;
      return {
        ...w,
        current_rank: lastPoint?.rank ?? w.best_rank_in_period,
        sparkline: sp,
      };
    });

    // 장르 트렌드
    const genre7dMap = new Map<string, number>();
    for (const r of genre7dRows) {
      if (r.genre_kr) genre7dMap.set(String(r.genre_kr), Number(r.cnt));
    }

    const genreTrends: GenreTrend[] = genreCurrRows
      .filter((r) => r.genre_kr)
      .map((r) => {
        const gkr = String(r.genre_kr);
        const prevCount = genre7dMap.get(gkr) || 0;
        const currCount = Number(r.cnt);
        return {
          genre: String(r.genre || ""),
          genre_kr: gkr,
          current_count: currCount,
          prev_count: prevCount,
          delta: currCount - prevCount,
          riverse_count: Number(r.rv_cnt || 0),
          top_work: r.top_title ? {
            title: String(r.top_title),
            platform: String(r.top_platform),
            rank: Number(r.best_rank),
            is_riverse: !!r.top_is_rv,
            unified_work_id: r.top_uwid ?? null,
          } : null,
        };
      });

    // 플랫폼 비교
    const platformComparison: PlatformComparison[] = platformCompRows.map((r) => ({
      platform: String(r.platform),
      platform_name: platformName(String(r.platform)),
      platform_color: PLATFORM_COLORS[r.platform] || "#666",
      total_ranked: Number(r.total_ranked),
      riverse_count: Number(r.riverse_count),
      share_pct: r.total_ranked > 0 ? Math.round((r.riverse_count / r.total_ranked) * 100) : 0,
      avg_riverse_rank: r.avg_rv_rank ? Number(r.avg_rv_rank) : null,
    }));

    // ── 리버스 / 타사 분리 ──

    const riverseRising = allRising.filter((w) => w.is_riverse).slice(0, 5);
    const riverseNew = allNewEntries.filter((w) => w.is_riverse).slice(0, 5);
    const riverseMulti = allMulti.filter((w) => w.is_riverse).slice(0, 5);
    const riverseFalling = allFalling.filter((w) => w.is_riverse).slice(0, 5);

    const marketRising = allRising.slice(0, 8);
    const marketNew = allNewEntries.slice(0, 8);
    const marketMulti = allMulti.filter((w) => !w.is_riverse).slice(0, 5);
    const marketFalling = allFalling.filter((w) => !w.is_riverse).slice(0, 5);

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
      date_7d_ago: date7dAgo,
      kpi,
      riverse: {
        summary: riverseSummaryText,
        total_in_rankings: totalRiverseInRankings,
        active_platforms: activePlatforms,
        top_ranked: topRiverseWithSparkline,
        rising: riverseRising,
        falling: riverseFalling,
        new_entries: riverseNew,
        multi_platform: riverseMulti,
        platform_share: platformShare,
        consistent_performers: consistentPerformers.filter((p) => p.is_riverse).slice(0, 5),
      },
      market: {
        summary: marketSummaryText,
        top_rising: marketRising,
        top_falling: marketFalling,
        new_entries: marketNew,
        multi_platform: marketMulti,
        top1_works: top1Works,
      },
      genre_trends: genreTrends,
      platform_comparison: platformComparison,
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

// ─── 리버스 요약문 ──────────────────

function buildRiverseSummary(d: {
  totalInRankings: number;
  activePlatforms: number;
  topRanked: RankedWork[];
  rising: RisingWork[];
  platformShare: PlatformShare[];
}): string {
  const lines: string[] = [];
  lines.push(`${d.activePlatforms}개 플랫폼, ${d.totalInRankings}건 랭킹 진입`);

  if (d.topRanked.length > 0) {
    const t = d.topRanked[0];
    if (t.rank <= 3) {
      lines.push(`${t.platform_name} ${t.rank}위 «${t.title}» — 선두 유지`);
    } else {
      lines.push(`최고 순위: ${t.platform_name} ${t.rank}위 «${t.title}»`);
    }
  }

  const activeShares = d.platformShare.filter((p) => p.riverse_count > 0);
  if (activeShares.length > 0) {
    const top = activeShares.reduce((a, b) => (a.share_pct > b.share_pct ? a : b));
    if (top.share_pct >= 3) {
      lines.push(`${top.platform_name} 점유율 ${top.share_pct}% 최고`);
    }
  }

  if (d.rising.length > 0) {
    const r = d.rising[0];
    lines.push(`급상승 «${r.title}» ${r.prev_rank}→${r.curr_rank}위 (+${r.change})`);
  }

  return lines.join("\n");
}

// ─── 시장 전체 요약문 ──────────────────

function buildMarketSummary(d: {
  rising: RisingWork[];
  newEntries: NewEntry[];
  multiPlatform: MultiPlatformWork[];
  top1Works: { title: string; title_kr: string | null; platform: string; platform_name: string; is_riverse: boolean }[];
}): string {
  const lines: string[] = [];

  if (d.rising.length > 0) {
    const r = d.rising[0];
    lines.push(`최대 급상승 «${r.title}» +${r.change}계단 (${r.platform_name})`);
    if (d.rising.length > 2) {
      lines.push(`5위 이상 상승 ${d.rising.length}작품`);
    }
  }

  if (d.newEntries.length > 0) {
    const top = d.newEntries.filter((w) => w.rank <= 3);
    if (top.length > 0) {
      const w = top[0];
      lines.push(`신규 주목 «${w.title}» ${w.platform_name} ${w.rank}위 진입`);
    }
    lines.push(`TOP 30 신규 ${d.newEntries.length}작품`);
  }

  if (d.multiPlatform.length > 0) {
    const m = d.multiPlatform[0];
    lines.push(`«${m.title}» ${m.platform_count}개 플랫폼 동시 랭크인`);
  }

  return lines.join("\n");
}
