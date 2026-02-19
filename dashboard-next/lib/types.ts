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
