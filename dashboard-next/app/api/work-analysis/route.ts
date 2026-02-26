import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";
import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || "",
});

const PLATFORM_NAMES: Record<string, string> = {
  piccoma: "픽코마", linemanga: "라인망가", mechacomic: "메챠코믹",
  cmoa: "코믹시모아", comico: "코미코", renta: "렌타",
  booklive: "북라이브", ebookjapan: "이북재팬", lezhin: "레진코믹스",
  beltoon: "벨툰", unext: "U-NEXT", asura: "Asura Scans",
};

export const maxDuration = 60; // Vercel serverless timeout

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const idParam = searchParams.get("id");
  const refresh = searchParams.get("refresh") === "true";
  const cacheOnly = searchParams.get("cache_only") === "true";

  if (!idParam) {
    return NextResponse.json({ error: "id required" }, { status: 400 });
  }

  const id = parseInt(idParam, 10);
  if (isNaN(id)) {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  }

  // 캐시 조회 (refresh가 아닌 경우)
  if (!refresh) {
    const cached = await sql`
      SELECT analysis, data_summary, generated_at
      FROM work_analyses
      WHERE unified_work_id = ${id}
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

  if (!process.env.ANTHROPIC_API_KEY) {
    return NextResponse.json({ error: "ANTHROPIC_API_KEY not configured" }, { status: 500 });
  }

  // 1. unified_works 마스터 정보
  const metaRows = await sql`
    SELECT id, title_kr, title_canonical, author, artist, publisher,
           genre, genre_kr, tags, description, is_riverse
    FROM unified_works WHERE id = ${id} LIMIT 1
  `;

  if (metaRows.length === 0) {
    return NextResponse.json({ error: "work not found" }, { status: 404 });
  }

  const meta = metaRows[0];

  // 2. 플랫폼별 works 조회
  const worksRows = await sql`
    SELECT platform, title, best_rank, rating, review_count, hearts, favorites,
           first_seen_date, last_seen_date, label
    FROM works WHERE unified_work_id = ${id}
  `;

  // 3. 모든 플랫폼 랭킹 추이 한 번에 조회 (N+1 제거)
  const allRankRows = await sql`
    SELECT r.platform, r.title, r.date, r.rank::int as rank
    FROM rankings r
    INNER JOIN works w ON w.platform = r.platform AND w.title = r.title
    WHERE w.unified_work_id = ${id}
      AND COALESCE(r.sub_category, '') = ''
    ORDER BY r.platform, r.date DESC
  `;

  // 플랫폼별로 그룹핑 (최근 14일만)
  const rankByPlatform = new Map<string, { date: string; rank: number }[]>();
  for (const r of allRankRows) {
    const key = r.platform;
    if (!rankByPlatform.has(key)) rankByPlatform.set(key, []);
    const arr = rankByPlatform.get(key)!;
    if (arr.length < 14) arr.push({ date: r.date, rank: r.rank });
  }

  const rankData: string[] = [];
  for (const w of worksRows) {
    const pName = PLATFORM_NAMES[w.platform] || w.platform;
    const parts = [`[${pName}]`];
    if (w.best_rank) parts.push(`최고${w.best_rank}위`);
    if (w.rating) parts.push(`평점${w.rating}`);
    if (w.review_count) parts.push(`리뷰${w.review_count}건`);
    if (w.hearts) parts.push(`하트${w.hearts.toLocaleString()}`);
    if (w.favorites) parts.push(`즐겨찾기${w.favorites.toLocaleString()}`);
    if (w.first_seen_date) parts.push(`등장${w.first_seen_date}`);
    if (w.last_seen_date) parts.push(`최근${w.last_seen_date}`);
    if (w.label) parts.push(`레이블:${w.label}`);

    const rows = rankByPlatform.get(w.platform);
    if (rows && rows.length > 0) {
      const trend = rows.map((r) => `${r.date}: ${r.rank}위`).join(", ");
      parts.push(`\n  추이: ${trend}`);
    }
    rankData.push(parts.join(", "));
  }

  // 4. 리뷰 키워드 분석 (원문 인용 대신 통계적 요약)
  const reviewRows = await sql`
    SELECT r.platform, r.body, r.rating, r.likes_count
    FROM reviews r
    INNER JOIN works w ON w.platform = r.platform AND w.title = r.work_title
    WHERE w.unified_work_id = ${id}
      AND r.is_spoiler = FALSE AND LENGTH(r.body) > 10
    ORDER BY r.likes_count DESC, r.reviewed_at DESC NULLS LAST
    LIMIT 50
  `;

  // 긍정/부정 리뷰 요약 (원문 노출 대신 평점별 건수 + 짧은 키워드)
  const positiveCount = reviewRows.filter((r) => r.rating >= 4).length;
  const negativeCount = reviewRows.filter((r) => r.rating && r.rating <= 2).length;
  const neutralCount = reviewRows.filter((r) => r.rating === 3).length;
  const avgBodyLen = reviewRows.length > 0
    ? Math.round(reviewRows.reduce((s, r) => s + r.body.length, 0) / reviewRows.length)
    : 0;
  const highLikesCount = reviewRows.filter((r) => r.likes_count >= 10).length;

  const reviewSummary = `긍정(★4~5): ${positiveCount}건, 부정(★1~2): ${negativeCount}건, 중립(★3): ${neutralCount}건
좋아요 10+ 인기 리뷰: ${highLikesCount}건, 평균 리뷰 길이: ${avgBodyLen}자
총 샘플: ${reviewRows.length}건 (좋아요순 상위 50건)`;

  // 5. 리뷰 통계
  const statsRows = await sql`
    SELECT
      COUNT(*)::int as total,
      AVG(r.rating)::numeric(3,1) as avg_rating,
      COUNT(CASE WHEN r.rating = 5 THEN 1 END)::int as star5,
      COUNT(CASE WHEN r.rating = 4 THEN 1 END)::int as star4,
      COUNT(CASE WHEN r.rating = 3 THEN 1 END)::int as star3,
      COUNT(CASE WHEN r.rating = 2 THEN 1 END)::int as star2,
      COUNT(CASE WHEN r.rating = 1 THEN 1 END)::int as star1
    FROM reviews r
    INNER JOIN works w ON w.platform = r.platform AND w.title = r.work_title
    WHERE w.unified_work_id = ${id}
  `;

  // 6. 독자층 분석
  const demoRows = await sql`
    SELECT r.reviewer_info, COUNT(*)::int as cnt
    FROM reviews r
    INNER JOIN works w ON w.platform = r.platform AND w.title = r.work_title
    WHERE w.unified_work_id = ${id}
      AND r.reviewer_info IS NOT NULL AND r.reviewer_info != ''
    GROUP BY r.reviewer_info
    ORDER BY cnt DESC LIMIT 10
  `;

  const stats = statsRows[0] || {};
  const demographics = demoRows.map((d) => `${d.reviewer_info}: ${d.cnt}명`).join(", ");

  // 검색 쿼리를 위한 제목 (일본어 + 한국어)
  const titleJa = worksRows.length > 0 ? worksRows[0].title : meta.title_canonical;
  const titleKr = meta.title_kr || "";

  const prompt = `당신은 일본 디지털 만화/웹툰 시장 전문 애널리스트입니다.
아래 정량 데이터를 근거로 분석 보고서를 작성하세요.

웹 검색으로 보완할 키워드:
1. "${titleJa} 漫画"
${titleKr ? `2. "${titleKr} 웹툰"` : ""}

[정량 데이터]
제목: ${titleKr || meta.title_canonical || "미상"} / ${titleJa}
작가: ${meta.author || "미상"} / 작화: ${meta.artist || "미상"}
출판사: ${meta.publisher || "미상"}
장르: ${meta.genre_kr || meta.genre || "미분류"}
태그: ${meta.tags || "없음"}
한국 원작: ${meta.is_riverse ? "예" : "아니오"}

플랫폼 전개 (${worksRows.length}개 플랫폼):
${rankData.join("\n") || "데이터 없음"}

리뷰 통계: 총 ${stats.total || 0}건, 평균 ${stats.avg_rating || "N/A"}
분포: ★5=${stats.star5||0} ★4=${stats.star4||0} ★3=${stats.star3||0} ★2=${stats.star2||0} ★1=${stats.star1||0}
${reviewSummary}
독자층: ${demographics || "데이터 없음"}

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
플랫폼 전개 현황과 랭킹 데이터 기반 분석. 구체적 수치 인용.

2. 독자 반응
리뷰 통계(평점 분포, 긍정/부정 비율) 기반 분석. 리뷰 원문 인용 금지.

3. 타겟 독자층
성별/연령 데이터가 있으면 구체적으로. 없으면 "데이터 부족으로 판단 보류"로 짧게 처리.

4. 경쟁력 요약
데이터에서 읽히는 강점과 약점만 간결하게.

5. 사업 전망
확인된 사실(애니화, 드라마화 등) 위주. 추측은 최소화.`;

  try {
    const response = await anthropic.messages.create({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 4096,
      tools: [
        {
          type: "web_search_20250305" as const,
          name: "web_search" as const,
          max_uses: 3,
        },
      ],
      messages: [{ role: "user", content: prompt }],
    });

    // web_search 사용 시 content 블록에 텍스트와 tool_use가 섞여 나옴
    const text = response.content
      .filter((block): block is Anthropic.TextBlock => block.type === "text")
      .map((block) => block.text)
      .join("");

    const dataSummary = {
      platform_count: worksRows.length,
      review_total: stats.total || 0,
      avg_rating: stats.avg_rating || null,
      demographics: demographics || null,
    };

    // DB에 분석 결과 저장 (UPSERT)
    await sql`
      INSERT INTO work_analyses (unified_work_id, analysis, data_summary, generated_at)
      VALUES (${id}, ${text}, ${JSON.stringify(dataSummary)}, NOW())
      ON CONFLICT (unified_work_id)
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
    console.error("AI analysis error:", error);
    return NextResponse.json(
      { error: "AI 분석 생성 실패" },
      { status: 500 }
    );
  }
}
