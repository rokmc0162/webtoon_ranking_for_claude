import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";

// 리뷰 페이지네이션 API: offset/limit 기반 더보기 지원
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const platform = searchParams.get("platform") || "";
  const title = searchParams.get("title") || "";
  const offset = parseInt(searchParams.get("offset") || "0", 10);
  const limit = parseInt(searchParams.get("limit") || "50", 10);

  if (!platform || !title) {
    return NextResponse.json(
      { error: "platform and title required" },
      { status: 400 }
    );
  }

  const safeLimit = Math.min(limit, 200);

  const [rows, countRows] = await Promise.all([
    sql`
      SELECT reviewer_name, reviewer_info, body, rating,
             likes_count, is_spoiler, reviewed_at
      FROM reviews
      WHERE platform = ${platform} AND work_title = ${title}
      ORDER BY reviewed_at DESC NULLS LAST, collected_at DESC
      OFFSET ${offset}
      LIMIT ${safeLimit}
    `,
    sql`
      SELECT COUNT(*)::int as total
      FROM reviews
      WHERE platform = ${platform} AND work_title = ${title}
    `,
  ]);

  const reviews = rows.map((r) => ({
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

  return NextResponse.json(
    {
      reviews,
      total: countRows[0]?.total || 0,
      offset,
      limit: safeLimit,
      hasMore: offset + safeLimit < (countRows[0]?.total || 0),
    },
    {
      headers: {
        "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600",
      },
    }
  );
}
