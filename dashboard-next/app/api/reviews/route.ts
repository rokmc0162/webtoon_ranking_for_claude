import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const platform = searchParams.get("platform") || "";
  const title = searchParams.get("title") || "";

  if (!platform || !title) {
    return NextResponse.json(
      { error: "platform and title required" },
      { status: 400 }
    );
  }

  // 작품 메타데이터
  const metaRows = await sql`
    SELECT author, publisher, label, tags, description,
           hearts, favorites, rating, review_count
    FROM works
    WHERE platform = ${platform} AND title = ${title}
    LIMIT 1
  `;

  const metadata = metaRows.length > 0
    ? {
        author: metaRows[0].author || "",
        publisher: metaRows[0].publisher || "",
        label: metaRows[0].label || "",
        tags: metaRows[0].tags || "",
        description: metaRows[0].description || "",
        hearts: metaRows[0].hearts ?? null,
        favorites: metaRows[0].favorites ?? null,
        rating: metaRows[0].rating ? Number(metaRows[0].rating) : null,
        review_count: metaRows[0].review_count ?? null,
      }
    : {
        author: "",
        publisher: "",
        label: "",
        tags: "",
        description: "",
        hearts: null,
        favorites: null,
        rating: null,
        review_count: null,
      };

  // 리뷰 목록 (최신순, 전체)
  const reviewRows = await sql`
    SELECT reviewer_name, reviewer_info, body, rating,
           likes_count, is_spoiler, reviewed_at
    FROM reviews
    WHERE platform = ${platform} AND work_title = ${title}
    ORDER BY reviewed_at DESC NULLS LAST, collected_at DESC
    LIMIT 500
  `;

  const reviews = reviewRows.map((r) => ({
    reviewer_name: r.reviewer_name || "",
    reviewer_info: r.reviewer_info || "",
    body: r.body || "",
    rating: r.rating ?? null,
    likes_count: r.likes_count ?? 0,
    is_spoiler: r.is_spoiler ?? false,
    reviewed_at: r.reviewed_at
      ? new Date(r.reviewed_at).toISOString().split("T")[0]
      : null,
  }));

  return NextResponse.json({ metadata, reviews });
}
