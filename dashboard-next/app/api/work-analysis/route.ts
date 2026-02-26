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

export const maxDuration = 30; // Vercel serverless timeout

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const idParam = searchParams.get("id");

  if (!idParam) {
    return NextResponse.json({ error: "id required" }, { status: 400 });
  }

  const id = parseInt(idParam, 10);
  if (isNaN(id)) {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
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

  // 3. 각 플랫폼별 최근 랭킹 추이 (최근 14일)
  const rankData: string[] = [];
  for (const w of worksRows) {
    const rows = await sql`
      SELECT date, rank::int as rank
      FROM rankings
      WHERE title = ${w.title} AND platform = ${w.platform}
        AND COALESCE(sub_category, '') = ''
      ORDER BY date DESC LIMIT 14
    `;
    if (rows.length > 0) {
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

  const prompt = `당신은 일본 웹툰/만화 시장 분석 전문가입니다.

먼저 이 작품에 대해 웹 검색을 수행하여 최신 정보를 수집한 뒤, 우리 DB 데이터와 종합하여 분석해주세요.

## 검색 지시
아래 키워드로 웹 검색을 해주세요:
1. "${titleJa} 漫画 評価" (일본어 제목으로 평가/리뷰 검색)
${titleKr ? `2. "${titleKr} 웹툰" (한국어 제목으로 검색)` : ""}
3. "${titleJa} ピッコマ" 또는 "${titleJa} LINEマンガ" (플랫폼에서의 인기도)

## 우리 DB 데이터

### 작품 정보
- 제목: ${titleKr || meta.title_canonical || "미상"} (일본어: ${titleJa})
- 작가: ${meta.author || "미상"} / 작화: ${meta.artist || "미상"}
- 출판사: ${meta.publisher || "미상"}
- 장르: ${meta.genre_kr || meta.genre || "미분류"}
- 태그: ${meta.tags || "없음"}
- 리버스(한국 원작) 여부: ${meta.is_riverse ? "예" : "아니오"}
- 작품 설명: ${meta.description ? meta.description.slice(0, 300) : "없음"}

### 플랫폼별 현황 (${worksRows.length}개 플랫폼)
${rankData.join("\n\n") || "데이터 없음"}

### 리뷰/평가 통계
- 총 리뷰 수: ${stats.total || 0}건
- 평균 평점: ${stats.avg_rating || "N/A"}
- 평점 분포: ★5=${stats.star5||0}, ★4=${stats.star4||0}, ★3=${stats.star3||0}, ★2=${stats.star2||0}, ★1=${stats.star1||0}

### 독자층 (성별/연령 분포)
${demographics || "데이터 없음"}

### 리뷰 샘플 (좋아요 높은 순)
${reviewSamples || "리뷰 없음"}

---

웹 검색 결과와 위 DB 데이터를 종합하여 아래 형식으로 분석을 작성해주세요.
- DB 데이터에 근거한 내용은 그대로 사용
- 웹 검색에서 얻은 추가 정보는 "(웹 검색 기반)" 등으로 출처 표시
- 데이터가 없는 항목은 추측하지 말고 "데이터 부족"으로 표시
- 각 섹션은 간결하게 3-5문장으로

### 1. 작품 현황 요약
(시장 위치, 멀티 플랫폼 현황, 웹에서 확인된 최신 동향)

### 2. 독자 반응 분석
(리뷰 데이터 + 웹에서 확인된 평판)

### 3. 주요 독자층
(성별/연령 데이터 기반, 없으면 "데이터 부족")

### 4. 강점과 약점
(데이터 기반 장단점)

### 5. 향후 전망
(랭킹 추이 + 웹 검색에서 확인된 연재/미디어 동향)`;

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

    return NextResponse.json({
      analysis: text,
      data_summary: {
        platform_count: worksRows.length,
        review_total: stats.total || 0,
        avg_rating: stats.avg_rating || null,
        demographics: demographics || null,
      },
    });
  } catch (error) {
    console.error("AI analysis error:", error);
    return NextResponse.json(
      { error: "AI 분석 생성 실패" },
      { status: 500 }
    );
  }
}
