import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";
import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || "",
});

export const maxDuration = 60; // Vercel serverless timeout

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

  if (!process.env.ANTHROPIC_API_KEY) {
    return NextResponse.json({ error: "ANTHROPIC_API_KEY not configured" }, { status: 500 });
  }

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
    .filter((r) => !r.sub_category || r.sub_category === "")
    .map((r) => ({ date: r.date, rank: r.rank }));

  // 3. 리뷰 샘플 (최근 50건 — AI에 보낼 양)
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
  const titleKr = meta.title_kr || "";
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

  // 프롬프트 조합
  const rankTrend = overallRanks.length > 0
    ? overallRanks.slice(0, 14).map((r) => `${r.date}: ${r.rank}위`).join(", ")
    : "데이터 없음";

  const rankBest = meta.best_rank || "N/A";
  const rankAvg = overallRanks.length > 0
    ? (overallRanks.reduce((s, r) => s + r.rank, 0) / overallRanks.length).toFixed(1)
    : "N/A";

  const stats = reviewStatsRows[0] || {};
  const demographics = demographicRows.map((d) => `${d.reviewer_info}: ${d.cnt}명`).join(", ");

  const reviewSamples = reviewRows
    .filter((r) => !r.is_spoiler && r.body.length > 10)
    .slice(0, 30)
    .map((r) => {
      const info = r.reviewer_info ? `[${r.reviewer_info}]` : "";
      const star = r.rating ? `★${r.rating}` : "";
      const likes = r.likes_count > 0 ? `(좋아요 ${r.likes_count})` : "";
      return `${info}${star}${likes} ${r.body.slice(0, 200)}`;
    })
    .join("\n");

  const crossInfo = crossRows.length > 0
    ? crossRows.map((c) => `${c.platform}: 최고${c.best_rank || "?"}위, 평점${c.rating || "?"}`).join("; ")
    : "이 플랫폼에서만 확인됨";

  const platformNames: Record<string, string> = {
    piccoma: "픽코마", linemanga: "라인망가", mechacomic: "메챠코믹",
    cmoa: "코믹시모아", comico: "코미코", renta: "렌타",
    booklive: "북라이브", ebookjapan: "이북재팬", lezhin: "레진코믹스",
    beltoon: "벨툰", unext: "U-NEXT", asura: "Asura Scans",
  };

  const pName = platformNames[platform] || platform;

  const prompt = `당신은 일본 만화/웹툰 시장을 10년 이상 분석해온 시니어 콘텐츠 애널리스트입니다.
아래 데이터와 웹 검색 결과를 종합하여, 콘텐츠 사업 의사결정자에게 보고하는 수준의 분석을 작성하세요.

웹 검색 키워드:
1. "${meta.title} 漫画 評価"
${titleKr ? `2. "${titleKr} 웹툰"` : ""}
3. "${meta.title} ${pName}"

[데이터]
제목: ${meta.title} / ${titleKr || "한국어명 없음"}
플랫폼: ${pName}
작가: ${meta.author || "미상"} / 출판사: ${meta.publisher || "미상"}
장르: ${meta.genre_kr || meta.genre || "미분류"}
태그: ${meta.tags || "없음"}
한국 원작 여부: ${meta.is_riverse ? "예" : "아니오"}
시놉시스: ${meta.description ? meta.description.slice(0, 300) : "없음"}

랭킹: 최고 ${rankBest}위, 평균 ${rankAvg}위 (${meta.first_seen_date || "?"} ~ ${meta.last_seen_date || "?"})
추이: ${rankTrend}

리뷰 통계: 총 ${stats.total || 0}건, 평균 ${stats.avg_rating || "N/A"}, 분포 ★5=${stats.star5||0} ★4=${stats.star4||0} ★3=${stats.star3||0} ★2=${stats.star2||0} ★1=${stats.star1||0}
독자층: ${demographics || "데이터 없음"}
크로스 플랫폼: ${crossInfo}

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
${pName} 내 이 작품의 현재 위치. 랭킹 추이에서 읽히는 경쟁력. 크로스 플랫폼 전개 상황.

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
      rank_best: rankBest,
      rank_avg: rankAvg,
      review_total: stats.total || 0,
      avg_rating: stats.avg_rating || null,
      demographics: demographics || null,
      cross_platform_count: crossRows.length,
    };

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
    console.error("AI analysis error:", error);
    return NextResponse.json(
      { error: "AI 분석 생성 실패" },
      { status: 500 }
    );
  }
}
