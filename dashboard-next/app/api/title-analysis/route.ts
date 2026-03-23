import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";

let Anthropic: typeof import("@anthropic-ai/sdk").default | null = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  Anthropic = require("@anthropic-ai/sdk").default;
} catch {
  // @anthropic-ai/sdk not installed — data-based fallback only
}

export const maxDuration = 60; // Vercel serverless timeout

// ---------- 데이터 기반 분석 생성 (AI 없이) ----------
function generateDataAnalysis(
  meta: Record<string, unknown>,
  overallRanks: { date: string; rank: number }[],
  stats: Record<string, unknown>,
  filteredReviews: { rating: number; likes_count: number; body: string }[],
  demographics: string,
  crossRows: Record<string, unknown>[],
  pName: string,
) {
  const rankBest = meta.best_rank || "N/A";
  const rankAvg = overallRanks.length > 0
    ? (overallRanks.reduce((s, r) => s + r.rank, 0) / overallRanks.length).toFixed(1)
    : "N/A";

  // 순위 변동 계산
  let rankChange = "—";
  if (overallRanks.length >= 2) {
    const latest = overallRanks[0].rank;
    const oldest = overallRanks[overallRanks.length - 1].rank;
    const diff = oldest - latest; // 양수 = 상승(순위 숫자 감소)
    if (diff > 0) rankChange = `▲${diff} (상승)`;
    else if (diff < 0) rankChange = `▼${Math.abs(diff)} (하락)`;
    else rankChange = "— (유지)";
  }

  // 추적 기간 계산
  let trackingDays = 0;
  if (overallRanks.length >= 2) {
    const latest = new Date(overallRanks[0].date);
    const oldest = new Date(overallRanks[overallRanks.length - 1].date);
    trackingDays = Math.round((latest.getTime() - oldest.getTime()) / (1000 * 60 * 60 * 24));
  }

  // 최근 14일 랭킹 트렌드 텍스트
  const recentRanks = overallRanks.slice(0, 14);
  const trendText = recentRanks.length > 0
    ? recentRanks.map((r) => `${r.date}: ${r.rank}위`).join("\n")
    : "데이터 없음";

  // 리뷰 키워드 추출 (간단한 빈도 분석)
  const positiveCount = filteredReviews.filter((r) => r.rating >= 4).length;
  const negativeCount = filteredReviews.filter((r) => r.rating && r.rating <= 2).length;

  // 크로스 플랫폼 정보
  const platformNames: Record<string, string> = {
    piccoma: "픽코마", linemanga: "라인망가", linemanga_app: "라인망가(앱)", mechacomic: "메챠코믹",
    cmoa: "코믹시모아", comico: "코미코", renta: "렌타",
    booklive: "북라이브", ebookjapan: "이북재팬", lezhin: "레진코믹스",
    beltoon: "벨툰", unext: "U-NEXT", asura: "Asura Scans",
  };
  const crossInfo = crossRows.length > 0
    ? crossRows.map((c) => {
        const cpName = platformNames[c.platform as string] || c.platform;
        return `${cpName}: 최고 ${c.best_rank || "?"}위, 평점 ${c.rating || "?"}`;
      }).join("\n")
    : "이 플랫폼에서만 확인됨";

  const sections: string[] = [];

  sections.push(`## 📊 작품 분석\n`);

  // 작품 정보
  sections.push(`### 작품 정보`);
  sections.push(`- 장르: ${(meta.genre_kr || meta.genre || "미분류") as string}`);
  sections.push(`- 작가: ${(meta.author || "미상") as string}`);
  if (meta.publisher) sections.push(`- 출판사: ${meta.publisher as string}`);
  if (meta.tags) sections.push(`- 태그: ${meta.tags as string}`);
  if (meta.description) {
    const desc = (meta.description as string).slice(0, 200);
    sections.push(`- 설명: ${desc}${(meta.description as string).length > 200 ? "..." : ""}`);
  }
  sections.push(`- 한국 원작: ${meta.is_riverse ? "예" : "아니오"}`);
  sections.push(`- 플랫폼: ${pName}`);
  sections.push(``);

  // 랭킹 추이
  sections.push(`### 랭킹 추이`);
  sections.push(`- 최고 순위: ${rankBest}위${overallRanks.length > 0 ? ` (${overallRanks.reduce((best, r) => r.rank < best.rank ? r : best, overallRanks[0]).date})` : ""}`);
  if (overallRanks.length > 0) {
    sections.push(`- 최근 순위: ${overallRanks[0].rank}위 (${overallRanks[0].date})`);
  }
  sections.push(`- 평균 순위: ${rankAvg}위`);
  sections.push(`- 순위 변동: ${rankChange}`);
  sections.push(`- 추적 기간: ${trackingDays > 0 ? `${trackingDays}일` : "데이터 부족"}`);
  if (meta.hearts) sections.push(`- 하트: ${(meta.hearts as number).toLocaleString()}`);
  if (meta.favorites) sections.push(`- 즐겨찾기: ${(meta.favorites as number).toLocaleString()}`);
  sections.push(``);

  // 랭킹 트렌드
  sections.push(`### 랭킹 트렌드 (최근 14일)`);
  sections.push(trendText);
  sections.push(``);

  // 리뷰 요약
  sections.push(`### 리뷰 요약`);
  sections.push(`- 총 리뷰: ${stats.total || 0}건`);
  sections.push(`- 평균 평점: ${stats.avg_rating || "N/A"} / 5.0`);
  sections.push(`- 평점 분포: ★5=${stats.star5||0} ★4=${stats.star4||0} ★3=${stats.star3||0} ★2=${stats.star2||0} ★1=${stats.star1||0}`);
  sections.push(`- 긍정(★4~5): ${positiveCount}건, 부정(★1~2): ${negativeCount}건`);
  if (demographics) {
    sections.push(`- 독자층: ${demographics}`);
  }
  sections.push(``);

  // 크로스 플랫폼
  if (crossRows.length > 0) {
    sections.push(`### 크로스 플랫폼 현황 (${crossRows.length}개 플랫폼)`);
    sections.push(crossInfo);
    sections.push(``);
  }

  return sections.join("\n");
}

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const platform = searchParams.get("platform") || "";
  const title = searchParams.get("title") || "";
  const refresh = searchParams.get("refresh") === "true";
  const cacheOnly = searchParams.get("cache_only") === "true";

  if (!platform || !title) {
    return NextResponse.json({ error: "platform and title required" }, { status: 400 });
  }

  // 캐시 조회 (refresh가 아닌 경우)
  if (!refresh) {
    const cached = await sql`
      SELECT analysis, data_summary, generated_at
      FROM work_analyses
      WHERE platform = ${platform} AND work_title = ${title}
      LIMIT 1
    `;
    if (cached.length > 0) {
      return NextResponse.json({
        analysis: cached[0].analysis,
        data_summary: cached[0].data_summary,
        generated_at: cached[0].generated_at,
        cached: true,
      });
    }
    // 캐시만 확인하는 경우 (마운트 시 자동 로드)
    if (cacheOnly) {
      return NextResponse.json({ analysis: null, cached: false });
    }
  }

  const useAI = !!(process.env.ANTHROPIC_API_KEY && Anthropic);

  // 1. 작품 메타데이터
  const metaRows = await sql`
    SELECT title, title_kr, genre, genre_kr, is_riverse,
           author, publisher, label, tags, description,
           hearts, favorites, rating, review_count,
           best_rank, first_seen_date, last_seen_date
    FROM works
    WHERE platform = ${platform} AND title = ${title}
    LIMIT 1
  `;

  if (metaRows.length === 0) {
    return NextResponse.json({ error: "title not found" }, { status: 404 });
  }

  const meta = metaRows[0];

  // 2. 랭킹 히스토리 (최근 30일)
  const rankRows = await sql`
    SELECT date, rank::int as rank, sub_category
    FROM rankings
    WHERE title = ${title} AND platform = ${platform}
    ORDER BY date DESC
    LIMIT 60
  `;

  const overallRanks = rankRows
    .filter((r: Record<string, unknown>) => !r.sub_category || r.sub_category === "")
    .map((r: Record<string, unknown>) => ({ date: r.date as string, rank: r.rank as number }));

  // 3. 리뷰 샘플 (최근 50건)
  const reviewRows = await sql`
    SELECT reviewer_name, reviewer_info, body, rating, likes_count, is_spoiler, reviewed_at
    FROM reviews
    WHERE platform = ${platform} AND work_title = ${title}
    ORDER BY likes_count DESC, reviewed_at DESC NULLS LAST
    LIMIT 50
  `;

  // 4. 리뷰 통계
  const reviewStatsRows = await sql`
    SELECT
      COUNT(*)::int as total,
      AVG(rating)::numeric(3,1) as avg_rating,
      COUNT(CASE WHEN rating = 5 THEN 1 END)::int as star5,
      COUNT(CASE WHEN rating = 4 THEN 1 END)::int as star4,
      COUNT(CASE WHEN rating = 3 THEN 1 END)::int as star3,
      COUNT(CASE WHEN rating = 2 THEN 1 END)::int as star2,
      COUNT(CASE WHEN rating = 1 THEN 1 END)::int as star1
    FROM reviews
    WHERE platform = ${platform} AND work_title = ${title}
  `;

  // 5. 독자층 분석 (reviewer_info에서 성별/연령 추출)
  const demographicRows = await sql`
    SELECT reviewer_info, COUNT(*)::int as cnt
    FROM reviews
    WHERE platform = ${platform} AND work_title = ${title}
      AND reviewer_info IS NOT NULL AND reviewer_info != ''
    GROUP BY reviewer_info
    ORDER BY cnt DESC
    LIMIT 10
  `;

  // 6. 크로스 플랫폼
  const titleKr = (meta.title_kr || "") as string;
  let crossRows;
  if (titleKr) {
    crossRows = await sql`
      SELECT platform, title, best_rank, rating, review_count
      FROM works
      WHERE platform != ${platform}
        AND (title = ${title} OR (title_kr = ${titleKr} AND title_kr != ''))
    `;
  } else {
    crossRows = await sql`
      SELECT platform, title, best_rank, rating, review_count
      FROM works
      WHERE platform != ${platform} AND title = ${title}
    `;
  }

  const rankBest = meta.best_rank || "N/A";
  const rankAvg = overallRanks.length > 0
    ? (overallRanks.reduce((s: number, r: { rank: number }) => s + r.rank, 0) / overallRanks.length).toFixed(1)
    : "N/A";

  const stats = reviewStatsRows[0] || {};
  const demographics = demographicRows.map((d: Record<string, unknown>) => `${d.reviewer_info}: ${d.cnt}명`).join(", ");

  const filteredReviews = reviewRows.filter((r: Record<string, unknown>) => !r.is_spoiler && (r.body as string).length > 10);
  const positiveCount = filteredReviews.filter((r: Record<string, unknown>) => (r.rating as number) >= 4).length;
  const negativeCount = filteredReviews.filter((r: Record<string, unknown>) => r.rating && (r.rating as number) <= 2).length;
  const neutralCount = filteredReviews.filter((r: Record<string, unknown>) => (r.rating as number) === 3).length;
  const highLikesCount = filteredReviews.filter((r: Record<string, unknown>) => (r.likes_count as number) >= 10).length;

  const platformNames: Record<string, string> = {
    piccoma: "픽코마", linemanga: "라인망가", linemanga_app: "라인망가(앱)", mechacomic: "메챠코믹",
    cmoa: "코믹시모아", comico: "코미코", renta: "렌타",
    booklive: "북라이브", ebookjapan: "이북재팬", lezhin: "레진코믹스",
    beltoon: "벨툰", unext: "U-NEXT", asura: "Asura Scans",
  };

  const pName = platformNames[platform] || platform;

  const dataSummary = {
    rank_best: rankBest,
    rank_avg: rankAvg,
    review_total: stats.total || 0,
    avg_rating: stats.avg_rating || null,
    demographics: demographics || null,
    cross_platform_count: crossRows.length,
  };

  // ---------- AI 분석 (ANTHROPIC_API_KEY가 있는 경우) ----------
  if (useAI) {
    const rankTrend = overallRanks.length > 0
      ? overallRanks.slice(0, 14).map((r: { date: string; rank: number }) => `${r.date}: ${r.rank}위`).join(", ")
      : "데이터 없음";

    const reviewSummary = `긍정(★4~5): ${positiveCount}건, 부정(★1~2): ${negativeCount}건, 중립(★3): ${neutralCount}건
좋아요 10+ 인기 리뷰: ${highLikesCount}건, 샘플: ${filteredReviews.length}건`;

    const crossInfo = crossRows.length > 0
      ? crossRows.map((c: Record<string, unknown>) => `${c.platform}: 최고${c.best_rank || "?"}위, 평점${c.rating || "?"}`).join("; ")
      : "이 플랫폼에서만 확인됨";

    const prompt = `당신은 일본 디지털 만화/웹툰 시장 전문 애널리스트입니다.
아래 정량 데이터를 근거로 분석 보고서를 작성하세요.

웹 검색으로 보완할 키워드:
1. "${meta.title} 漫画"
${titleKr ? `2. "${titleKr} 웹툰"` : ""}

[정량 데이터]
제목: ${meta.title} / ${titleKr || "한국어명 없음"}
플랫폼: ${pName}
작가: ${meta.author || "미상"} / 출판사: ${meta.publisher || "미상"}
장르: ${meta.genre_kr || meta.genre || "미분류"}
태그: ${meta.tags || "없음"}
한국 원작: ${meta.is_riverse ? "예" : "아니오"}

랭킹: 최고 ${rankBest}위, 평균 ${rankAvg}위 (${meta.first_seen_date || "?"} ~ ${meta.last_seen_date || "?"})
추이: ${rankTrend}
하트: ${meta.hearts || "N/A"}, 즐겨찾기: ${meta.favorites || "N/A"}

리뷰 통계: 총 ${stats.total || 0}건, 평균 ${stats.avg_rating || "N/A"}
분포: ★5=${stats.star5||0} ★4=${stats.star4||0} ★3=${stats.star3||0} ★2=${stats.star2||0} ★1=${stats.star1||0}
${reviewSummary}
독자층: ${demographics || "데이터 없음"}
크로스 플랫폼: ${crossInfo}

[절대 규칙]
1. 리뷰 원문이나 댓글을 절대 인용하지 마세요. 통계 수치만 활용하세요.
2. 데이터가 부족하면 솔직하게 "데이터 부족으로 판단 보류"라고 쓰세요. 억지로 추론하지 마세요.
3. 마크다운 기호 금지 (#, **, -, * 등). 섹션 제목은 "1. 제목" 형식만.
4. 서론, 도입부, 검색 과정 언급 없이 바로 "1. 시장 포지션"부터 시작.
5. 모호한 표현 금지. "~할 수 있습니다", "~로 보입니다" 대신 단정문.
6. 빈 줄로 문단을 구분. 한 문단은 2~4문장으로 구성.
7. 출처 표시 금지. (웹), (DB) 같은 태그 금지.

[섹션]

1. 시장 포지션
${pName} 내 위치와 랭킹 데이터 기반 분석. 크로스 플랫폼 현황.

2. 독자 반응
리뷰 통계(평점 분포, 긍정/부정 비율) 기반 분석. 리뷰 원문 인용 금지.

3. 타겟 독자층
성별/연령 데이터가 있으면 구체적으로. 없으면 "데이터 부족으로 판단 보류"로 짧게 처리.

4. 경쟁력 요약
데이터에서 읽히는 강점과 약점만 간결하게.

5. 사업 전망
확인된 사실(애니화, 드라마화 등) 위주. 추측은 최소화.`;

    try {
      const anthropicClient = new Anthropic!({
        apiKey: process.env.ANTHROPIC_API_KEY || "",
      });

      const response = await anthropicClient.messages.create({
        model: "claude-haiku-4-5-20251001",
        max_tokens: 4096,
        messages: [{ role: "user", content: prompt }],
      });

      type TextBlock = { type: "text"; text: string };
      let text = response.content
        .filter((block): block is TextBlock => block.type === "text")
        .map((block) => block.text)
        .join("");

      // "1." 이전 서론 제거 (웹 검색 과정 설명 등)
      const sectionIdx = text.indexOf("1.");
      if (sectionIdx > 0) text = text.slice(sectionIdx);

      // DB에 분석 결과 저장 (UPSERT)
      await sql`
        INSERT INTO work_analyses (platform, work_title, analysis, data_summary, generated_at)
        VALUES (${platform}, ${title}, ${text}, ${JSON.stringify(dataSummary)}, NOW())
        ON CONFLICT (platform, work_title)
        DO UPDATE SET analysis = EXCLUDED.analysis,
                      data_summary = EXCLUDED.data_summary,
                      generated_at = NOW()
      `;

      return NextResponse.json({
        analysis: text,
        data_summary: dataSummary,
        generated_at: new Date().toISOString(),
        cached: false,
      });
    } catch (error) {
      console.error("AI analysis error, falling back to data-based:", error);
      // AI 실패 시 데이터 기반 분석으로 폴백
    }
  }

  // ---------- 데이터 기반 분석 (AI 없이 또는 AI 실패 시) ----------
  const text = generateDataAnalysis(
    meta,
    overallRanks,
    stats,
    filteredReviews.map((r: Record<string, unknown>) => ({
      rating: r.rating as number,
      likes_count: r.likes_count as number,
      body: r.body as string,
    })),
    demographics,
    crossRows,
    pName,
  );

  // DB에 분석 결과 저장 (UPSERT)
  await sql`
    INSERT INTO work_analyses (platform, work_title, analysis, data_summary, generated_at)
    VALUES (${platform}, ${title}, ${text}, ${JSON.stringify(dataSummary)}, NOW())
    ON CONFLICT (platform, work_title)
    DO UPDATE SET analysis = EXCLUDED.analysis,
                  data_summary = EXCLUDED.data_summary,
                  generated_at = NOW()
  `;

  return NextResponse.json({
    analysis: text,
    data_summary: dataSummary,
    generated_at: new Date().toISOString(),
    cached: false,
  });
}
