export interface Ranking {
  rank: number;
  title: string;
  title_kr: string | null;
  genre: string | null;
  genre_kr: string | null;
  url: string;
  is_riverse: boolean;
  rank_change: number; // 양수=상승, 음수=하락, 999=NEW
  thumbnail_url?: string;
  thumbnail_base64?: string;
}

export interface PlatformInfo {
  id: string;
  name: string;
  color: string;
  logo: string; // public/ 경로
  sourceUrl: string;
  genres: Genre[];
}

export interface Genre {
  key: string; // DB sub_category 값 ('' = 종합)
  label: string; // 한국어 표시명
}

export interface RankHistory {
  date: string;
  rank: number | null;
  genre_rank: number | null;
}

export interface RankHistoryResponse {
  overall: RankHistory[];
  genre: string; // 장르명 (없으면 '')
}

export interface PlatformStats {
  total: number;
  riverse: number;
}

export interface WorkMetadata {
  author: string;
  publisher: string;
  label: string;
  tags: string;
  description: string;
  hearts: number | null;
  favorites: number | null;
  rating: number | null;
  review_count: number | null;
}

export interface Review {
  reviewer_name: string;
  reviewer_info: string;
  body: string;
  rating: number | null;
  likes_count: number;
  is_spoiler: boolean;
  reviewed_at: string | null;
}

export interface ReviewResponse {
  metadata: WorkMetadata;
  reviews: Review[];
}

// === 작품 상세 분석 페이지 타입 ===

export interface TitleDetailMetadata extends WorkMetadata {
  platform: string;
  title: string;
  title_kr: string;
  genre: string;
  genre_kr: string;
  is_riverse: boolean;
  url: string;
  thumbnail_url: string | null;
  thumbnail_base64: string | null;
  best_rank: number | null;
  first_seen_date: string | null;
  last_seen_date: string | null;
}

export interface CrossPlatformEntry {
  platform: string;
  platform_name: string;
  platform_color: string;
  best_rank: number | null;
  latest_rank: number | null;
  latest_date: string | null;
  rating: number | null;
  review_count: number | null;
  rank_history: { date: string; rank: number }[];
}

export interface ReviewStats {
  total: number;
  avg_rating: number | null;
  rating_distribution: Record<number, number>;
}

export interface TitleDetailResponse {
  metadata: TitleDetailMetadata;
  rankHistory: RankHistoryResponse;
  crossPlatform: CrossPlatformEntry[];
  reviewStats: ReviewStats;
  reviews: Review[];
}

// === 외부 데이터 (Phase 2) ===

export interface ExternalDataResponse {
  anilist: {
    score: number | null;
    popularity: number | null;
    members: number | null;
    status: string;
  } | null;
  mal: {
    score: number | null;
    members: number | null;
    rank: number | null;
    popularity: number | null;
  } | null;
  youtube: {
    pv_views: number | null;
    pv_count: number | null;
    total_views: number | null;
  } | null;
  google_trends: {
    interest_score: number | null;
    interest_avg_3m: number | null;
  } | null;
  reddit: {
    post_count: number | null;
    total_score: number | null;
    total_comments: number | null;
  } | null;
  bookwalker: {
    bw_rank: number | null;
    bw_rating: number | null;
    bw_review_count: number | null;
  } | null;
  pixiv: {
    fanart_count: number | null;
    fanart_bookmarks: number | null;
    fanart_views: number | null;
  } | null;
  amazon_jp: {
    amazon_rank: number | null;
    amazon_rating: number | null;
    amazon_review_count: number | null;
  } | null;
  twitter: {
    tweet_count: number | null;
    total_likes: number | null;
    total_retweets: number | null;
  } | null;
  collected_date: string | null;
}
