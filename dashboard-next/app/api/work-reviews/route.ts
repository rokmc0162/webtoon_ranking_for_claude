import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";

// 통합 작품 리뷰 페이지네이션 API: unified_work_id 기반
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const workId = searchParams.get("work_id") || "";
  const offset = parseInt(searchParams.get("offset") || "0", 10);
  const limit = parseInt(searchParams.get("limit") || "50", 10);

  if (!workId) {
    return NextResponse.json(
      { error: "work_id required" },
      { status: 400 }
    );
  }

  const numId = parseInt(workId, 10);
  const safeLimit = Math.min(limit, 200);

  const [rows, countRows] = await Promise.all([
    sql`
      SELECT r.platform, r.work_title, r.reviewer_name, r.reviewer_info,
             r.body, r.rating, r.likes_count, r.is_spoiler, r.reviewed_at
      FROM reviews r
      INNER JOIN works w ON w.platform = r.platform AND w.title = r.work_title
      WHERE w.unified_work_id = ${numId}
      ORDER BY r.reviewed_at DESC NULLS LAST, r.collected_at DESC
      OFFSET ${offset}
      LIMIT ${safeLimit}
    `,
    sql`
      SELECT COUNT(*)::int as total
      FROM reviews r
      INNER JOIN works w ON w.platform = r.platform AND w.title = r.work_title
      WHERE w.unified_work_id = ${numId}
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
    platform: r.platform || "",
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
