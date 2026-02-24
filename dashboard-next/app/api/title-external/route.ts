import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const title = searchParams.get("title") || "";

  if (!title) {
    return NextResponse.json({ error: "title required" }, { status: 400 });
  }

  const rows = await sql`
    SELECT DISTINCT ON (source, metric_name)
      source, metric_name, metric_value, metric_text, collected_date
    FROM external_data
    WHERE title = ${title}
    ORDER BY source, metric_name, collected_date DESC
  `;

  // 소스별로 그룹핑
  const grouped: Record<string, Record<string, { value: number | null; text: string }>> = {};
  let latestDate: string | null = null;

  for (const row of rows) {
    const source = row.source as string;
    const metricName = row.metric_name as string;
    if (!grouped[source]) grouped[source] = {};
    grouped[source][metricName] = {
      value: row.metric_value != null ? Number(row.metric_value) : null,
      text: (row.metric_text as string) || "",
    };
    const d = String(row.collected_date);
    if (!latestDate || d > latestDate) latestDate = d;
  }

  const result = {
    anilist: grouped.anilist
      ? {
          score: grouped.anilist.score?.value ?? null,
          popularity: grouped.anilist.popularity?.value ?? null,
          members: grouped.anilist.members?.value ?? null,
          status: grouped.anilist.status?.text ?? "",
        }
      : null,
    mal: grouped.mal
      ? {
          score: grouped.mal.score?.value ?? null,
          members: grouped.mal.members?.value ?? null,
          rank: grouped.mal.rank?.value ?? null,
          popularity: grouped.mal.popularity?.value ?? null,
        }
      : null,
    youtube: grouped.youtube
      ? {
          pv_views: grouped.youtube.pv_views?.value ?? null,
          pv_count: grouped.youtube.pv_count?.value ?? null,
          total_views: grouped.youtube.total_views?.value ?? null,
        }
      : null,
    google_trends: grouped.google_trends
      ? {
          interest_score: grouped.google_trends.interest_score?.value ?? null,
          interest_avg_3m: grouped.google_trends.interest_avg_3m?.value ?? null,
        }
      : null,
    reddit: grouped.reddit
      ? {
          post_count: grouped.reddit.post_count?.value ?? null,
          total_score: grouped.reddit.total_score?.value ?? null,
          total_comments: grouped.reddit.total_comments?.value ?? null,
        }
      : null,
    bookwalker: grouped.bookwalker
      ? {
          bw_rank: grouped.bookwalker.bw_rank?.value ?? null,
          bw_rating: grouped.bookwalker.bw_rating?.value ?? null,
          bw_review_count: grouped.bookwalker.bw_review_count?.value ?? null,
        }
      : null,
    pixiv: grouped.pixiv
      ? {
          fanart_count: grouped.pixiv.fanart_count?.value ?? null,
          fanart_bookmarks: grouped.pixiv.fanart_bookmarks?.value ?? null,
          fanart_views: grouped.pixiv.fanart_views?.value ?? null,
        }
      : null,
    amazon_jp: grouped.amazon_jp
      ? {
          amazon_rank: grouped.amazon_jp.amazon_rank?.value ?? null,
          amazon_rating: grouped.amazon_jp.amazon_rating?.value ?? null,
          amazon_review_count: grouped.amazon_jp.amazon_review_count?.value ?? null,
        }
      : null,
    twitter: grouped.twitter
      ? {
          tweet_count: grouped.twitter.tweet_count?.value ?? null,
          total_likes: grouped.twitter.total_likes?.value ?? null,
          total_retweets: grouped.twitter.total_retweets?.value ?? null,
        }
      : null,
    collected_date: latestDate,
  };

  return NextResponse.json(result);
}
