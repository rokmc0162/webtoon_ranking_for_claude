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
    SELECT platform, title, best_rank, rating, review_count, hearts, favorites
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
    const rows = rankByPlatform.get(w.platform);
    if (rows && rows.length > 0) {
      const trend = rows.map((r) => `${r.date}: ${r.rank}위`).join(", ");
      const pName = PLATFORM_NAMES[w.platform] || w.platform;
      rankData.push(`[${pName}] 최고${w.best_rank || "?"}위, 평점${w.rating || "-"}, 리뷰${w.review_count || 0}건\n  추이: ${trend}`);
    }
  }

  // 4. 리뷰 샘플 (좋아요 높은 순 30건)
  const reviewRows = await sql`
    SELECT r.platform, r.reviewer_info, r.body, r.rating, r.likes_count, r.is_spoiler
    FROM reviews r
    INNER JOIN works w ON w.platform = r.platform AND w.title = r.work_title
    WHERE w.unified_work_id = ${id}
      AND r.is_spoiler = FALSE AND LENGTH(r.body) > 10
    ORDER BY r.likes_count DESC, r.reviewed_at DESC NULLS LAST
    LIMIT 30
  `;

  const reviewSamples = reviewRows
    .map((r) => {
      const pName = PLATFORM_NAMES[r.platform] || r.platform;
      const info = r.reviewer_info ? `[${r.reviewer_info}]` : "";
      const star = r.rating ? `★${r.rating}` : "";
      const likes = r.likes_count > 0 ? `(좋아요 ${r.likes_count})` : "";
      return `${pName}${info}${star}${likes} ${r.body.slice(0, 200)}`;
    })
    .join("\n");

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

  const prompt = `당신은 일본 만화/웹툰 시장을 10년 이상 분석해온 시니어 콘텐츠 애널리스트입니다.
아래 데이터와 웹 검색 결과를 종합하여, 콘텐츠 사업 의사결정자에게 보고하는 수준의 분석을 작성하세요.

웹 검색 키워드:
1. "${titleJa} 漫画 評価"
${titleKr ? `2. "${titleKr} 웹툰"` : ""}
3. "${titleJa} ピッコマ" 또는 "${titleJa} LINEマンガ"

[데이터]
제목: ${titleKr || meta.title_canonical || "미상"} / ${titleJa}
작가: ${meta.author || "미상"} / 작화: ${meta.artist || "미상"}
출판사: ${meta.publisher || "미상"}
장르: ${meta.genre_kr || meta.genre || "미분류"}
태그: ${meta.tags || "없음"}
한국 원작 여부: ${meta.is_riverse ? "예" : "아니오"}
시놉시스: ${meta.description ? meta.description.slice(0, 300) : "없음"}

플랫폼별 현황 (${worksRows.length}개):
${rankData.join("\n") || "데이터 없음"}

리뷰 통계: 총 ${stats.total || 0}건, 평균 ${stats.avg_rating || "N/A"}, 분포 ★5=${stats.star5||0} ★4=${stats.star4||0} ★3=${stats.star3||0} ★2=${stats.star2||0} ★1=${stats.star1||0}
독자층: ${demographics || "데이터 없음"}

리뷰 샘플:
${reviewSamples || "없음"}

[작성 규칙]
- 마크다운 기호 절대 사용 금지. #, ##, ###, **, -, * 등 일체 사용하지 마세요.
- 섹션 제목은 "1. 시장 포지션" 처럼 번호와 제목만 쓰세요. 앞뒤에 기호 없이.
- 한 문장은 짧고 단정하게. 한 줄에 한 문장.
- 빈 줄로 문단을 구분하세요.
- 근거 없는 추측 금지. 데이터가 없으면 "확인 불가"로 처리.
- 출처 표시 하지 마세요. (웹), (DB) 같은 태그 붙이지 마세요.
- 전문 애널리스트가 경영진에게 브리핑하듯 쓰세요.
- 절대로 AI가 쓴 티가 나면 안 됩니다. "~할 수 있습니다", "~로 보입니다" 같은 모호한 표현 대신 단정적으로 쓰세요.

[섹션 구성]

1. 시장 포지션
현재 이 작품의 일본 디지털 만화 시장 내 위치. 멀티 플랫폼 전개 상황. 랭킹 추이에서 읽히는 경쟁력.

2. 독자 반응
리뷰 데이터와 웹 평판을 근거로 한 독자 평가. 긍정/부정 핵심 포인트.

3. 타겟 독자층
성별/연령 데이터가 있으면 구체적으로. 없으면 "확인 불가"로 짧게 처리.

4. 경쟁력 분석
이 작품이 시장에서 갖는 강점과 리스크. 동일 장르 내 차별화 요소.

5. 사업 전망
2차 사업(애니화, 드라마화, 굿즈, 게임 등) 가능성. 해외 전개 잠재력. 향후 랭킹/매출 추이 전망.`;

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
