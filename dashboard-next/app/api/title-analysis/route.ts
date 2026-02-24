import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";
import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || "",
});

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const platform = searchParams.get("platform") || "";
  const title = searchParams.get("title") || "";

  if (!platform || !title) {
    return NextResponse.json({ error: "platform and title required" }, { status: 400 });
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
    piccoma: "픽코마",
    linemanga: "라인망가",
    mechacomic: "메챠코믹",
    cmoa: "코믹시모아",
  };

  const prompt = `당신은 일본 웹툰/만화 시장 분석 전문가입니다. 아래 데이터를 기반으로 이 작품의 현황을 분석해주세요.

## 작품 정보
- 제목: ${meta.title} (${meta.title_kr || "한국어명 없음"})
- 플랫폼: ${platformNames[platform] || platform}
- 작가: ${meta.author || "미상"}
- 출판사: ${meta.publisher || "미상"}
- 장르: ${meta.genre_kr || meta.genre || "미분류"}
- 태그: ${meta.tags || "없음"}
- 리버스(한국 원작) 여부: ${meta.is_riverse ? "예" : "아니오"}
- 작품 설명: ${meta.description ? meta.description.slice(0, 300) : "없음"}

## 랭킹 데이터
- 최고 순위: ${rankBest}위
- 평균 순위: ${rankAvg}위
- 추적 기간: ${meta.first_seen_date || "?"} ~ ${meta.last_seen_date || "?"}
- 최근 추이 (날짜: 순위): ${rankTrend}

## 리뷰/평가 데이터
- 총 리뷰 수: ${stats.total || 0}건
- 평균 평점: ${stats.avg_rating || "N/A"}
- 평점 분포: ★5=${stats.star5||0}, ★4=${stats.star4||0}, ★3=${stats.star3||0}, ★2=${stats.star2||0}, ★1=${stats.star1||0}

## 독자층 (성별/연령 분포)
${demographics || "데이터 없음"}

## 크로스 플랫폼 현황
${crossInfo}

## 리뷰 샘플 (좋아요 높은 순)
${reviewSamples || "리뷰 없음"}

---

위 데이터를 분석하여 아래 형식으로 작성해주세요. 반드시 데이터에 근거하여 작성하고, 추측은 "~로 추정됩니다"로 표현하세요.

### 1. 작품 현황 요약
(2-3문장. 현재 이 작품이 시장에서 어떤 위치에 있는지)

### 2. 독자 반응 분석
(리뷰 내용과 평점을 근거로 독자들이 어떻게 평가하고 있는지)

### 3. 주요 독자층
(reviewer_info의 성별/연령 데이터와 리뷰 톤을 근거로)

### 4. 강점과 약점
(데이터 기반으로 이 작품의 장단점)

### 5. 향후 전망
(랭킹 추이, 리뷰 트렌드를 근거로 향후 예측)`;

  try {
    const response = await anthropic.messages.create({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 1500,
      messages: [{ role: "user", content: prompt }],
    });

    const text = response.content
      .filter((block) => block.type === "text")
      .map((block) => block.text)
      .join("");

    return NextResponse.json({
      analysis: text,
      data_summary: {
        rank_best: rankBest,
        rank_avg: rankAvg,
        review_total: stats.total || 0,
        avg_rating: stats.avg_rating || null,
        demographics: demographics || null,
        cross_platform_count: crossRows.length,
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
