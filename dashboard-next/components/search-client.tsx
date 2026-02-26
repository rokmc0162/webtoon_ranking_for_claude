"use client";

import { useState, useCallback, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Header } from "@/components/header";
import { RiverseBadge } from "@/components/riverse-badge";
import { Separator } from "@/components/ui/separator";
import { getPlatformById, isJapanesePlatform } from "@/lib/constants";

interface WorkEntry {
  platform: string;
  title: string;
  best_rank: number | null;
  rating: number | null;
  review_count: number | null;
  thumbnail_url: string | null;
  last_seen_date: string | null;
}

interface SearchResult {
  id: number;
  title_kr: string;
  title_en: string;
  title_canonical: string;
  author: string;
  genre_kr: string;
  is_riverse: boolean;
  thumbnail_url: string | null;
  works: WorkEntry[];
}

export function SearchClient() {
  const searchParams = useSearchParams();
  const initialQ = searchParams.get("q") || "";
  const [query, setQuery] = useState(initialQ);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [total, setTotal] = useState(0);

  const doSearch = useCallback(async (q: string) => {
    if (q.length < 2) return;
    setLoading(true);
    setSearched(true);
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      setResults(data.results || []);
      setTotal(data.total || 0);
    } catch {
      setResults([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSearch = useCallback(async () => {
    await doSearch(query);
  }, [query, doSearch]);

  // URL ?q= 파라미터로 들어온 경우 자동 검색
  useEffect(() => {
    if (initialQ && initialQ.length >= 2) {
      setQuery(initialQ);
      doSearch(initialQ);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQ]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-[900px] mx-auto px-3 sm:px-6">
        <Header />

        {/* 검색 바 */}
        <div className="mt-6 mb-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="작품명 / 작가명 / 출판사로 검색 (한/일/영)..."
              className="flex-1 px-4 py-2.5 rounded-lg border border-border bg-card text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              autoFocus
            />
            <button
              onClick={handleSearch}
              disabled={query.length < 2 || loading}
              className="px-5 py-2.5 rounded-lg bg-primary text-primary-foreground font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {loading ? "검색 중..." : "검색"}
            </button>
          </div>
          <p className="text-xs text-muted-foreground mt-1.5">
            전체 {total > 0 ? `${total}개 작품 발견` : "작품 DB에서 검색합니다"}
          </p>
        </div>

        {/* 검색 결과 */}
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-[100px] bg-muted rounded-lg animate-pulse" />
            ))}
          </div>
        ) : searched && results.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <p className="text-lg">검색 결과가 없습니다</p>
            <p className="text-sm mt-1">{`"${query}"에 해당하는 작품을 찾을 수 없습니다`}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {results.map((result) => (
              <SearchResultCard key={result.id} result={result} />
            ))}
          </div>
        )}

        {/* 푸터 */}
        <Separator className="mt-8" />
        <footer className="py-4 text-center text-xs text-muted-foreground">
          RIVERSE Inc. | 데이터: Supabase PostgreSQL | 매일 자동 수집
        </footer>
      </div>
    </div>
  );
}

function SearchResultCard({ result }: { result: SearchResult }) {
  const [imgError, setImgError] = useState(false);

  // 썸네일 프록시 URL — 일본 플랫폼 우선
  const jpWork = result.works.find((w) => isJapanesePlatform(w.platform));
  const thumbWork = jpWork || result.works[0];
  const thumbPlatform = thumbWork?.platform || "";
  const thumbTitle = thumbWork?.title || "";
  const proxyUrl = thumbPlatform
    ? `/api/thumbnail?platform=${encodeURIComponent(thumbPlatform)}&title=${encodeURIComponent(thumbTitle)}`
    : null;

  // 표시 제목: 한국어 > 정식 제목 > 영문
  const displayTitle = result.title_kr || result.title_canonical || result.title_en || "제목 없음";
  const subTitle = result.title_kr
    ? (result.title_canonical !== result.title_kr ? result.title_canonical : result.title_en)
    : null;

  return (
    <Link
      href={`/work/${result.id}`}
      className="block bg-card rounded-xl border p-4 hover:border-primary/30 hover:shadow-sm transition-all"
    >
      <div className="flex gap-4">
        {/* 썸네일 */}
        <div className="shrink-0">
          {proxyUrl && !imgError ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={proxyUrl}
              alt=""
              width={60}
              height={84}
              className="rounded-lg bg-muted"
              style={{ width: 60, height: 84, objectFit: "cover" }}
              referrerPolicy="no-referrer"
              onError={() => setImgError(true)}
            />
          ) : (
            <div className="w-[60px] h-[84px] bg-muted rounded-lg flex items-center justify-center text-xl">
              📖
            </div>
          )}
        </div>

        {/* 정보 */}
        <div className="flex-1 min-w-0">
          {/* 작품명 */}
          <div className="flex items-center gap-2">
            <span className="text-base font-bold text-foreground truncate">
              {displayTitle}
            </span>
            {result.is_riverse && <RiverseBadge />}
          </div>
          {subTitle && (
            <p className="text-xs text-muted-foreground mt-0.5 truncate">{subTitle}</p>
          )}
          {result.author && (
            <p className="text-xs text-muted-foreground mt-0.5">✍️ {result.author}</p>
          )}

          {/* 플랫폼별 정보 */}
          <div className="flex flex-wrap gap-1.5 mt-2">
            {result.works.map((w) => {
              const pInfo = getPlatformById(w.platform);
              return (
                <span
                  key={w.platform}
                  className="flex items-center gap-1 text-xs bg-muted px-2 py-0.5 rounded-full"
                >
                  <span
                    className="inline-block w-2 h-2 rounded-full"
                    style={{ backgroundColor: pInfo?.color || "#888" }}
                  />
                  <span className="font-medium">{pInfo?.name || w.platform}</span>
                  {w.best_rank && (
                    <span className="text-muted-foreground">
                      최고 {w.best_rank}위
                    </span>
                  )}
                  {w.rating && (
                    <span className="text-muted-foreground">
                      ★{w.rating.toFixed(1)}
                    </span>
                  )}
                </span>
              );
            })}
          </div>

          {/* 장르 */}
          {result.genre_kr && (
            <p className="text-xs text-muted-foreground mt-1">🏷️ {result.genre_kr}</p>
          )}
        </div>

        {/* 화살표 */}
        <div className="flex items-center text-muted-foreground">
          <span className="text-lg">›</span>
        </div>
      </div>
    </Link>
  );
}
