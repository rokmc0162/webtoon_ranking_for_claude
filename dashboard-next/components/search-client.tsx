"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { Header } from "@/components/header";
import { RiverseBadge } from "@/components/riverse-badge";
import { Separator } from "@/components/ui/separator";
import { getPlatformById, PLATFORMS } from "@/lib/constants";

interface SearchResult {
  title: string;
  title_kr: string | null;
  thumbnail_url: string | null;
  is_riverse: boolean;
  platforms: Array<{
    platform: string;
    rank: number;
    genre: string | null;
    genre_kr: string | null;
    url: string | null;
  }>;
}

interface SearchClientProps {
  latestDate: string;
}

export function SearchClient({ latestDate }: SearchClientProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [searchDate, setSearchDate] = useState(latestDate);

  const handleSearch = useCallback(async () => {
    if (query.length < 2) return;
    setLoading(true);
    setSearched(true);
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&date=${searchDate}`);
      const data = await res.json();
      setResults(data.results || []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [query, searchDate]);

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
              placeholder="작품명으로 검색 (일본어 또는 한국어)..."
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
            기준일: {searchDate} | 종합 랭킹에서 검색됩니다
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
            {results.map((result, idx) => (
              <SearchResultCard key={idx} result={result} />
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
  const proxyUrl = result.platforms.length > 0
    ? `/api/thumbnail?platform=${encodeURIComponent(result.platforms[0].platform)}&title=${encodeURIComponent(result.title)}`
    : null;

  const [imgError, setImgError] = useState(false);

  // 가장 높은 랭킹(낮은 숫자)
  const bestRank = Math.min(...result.platforms.map(p => p.rank));
  const bestPlatform = result.platforms.find(p => p.rank === bestRank);

  return (
    <div className="bg-card rounded-xl border p-4 hover:border-primary/30 transition-colors">
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
            <Link
              href={`/title/${bestPlatform?.platform || result.platforms[0]?.platform}/${encodeURIComponent(result.title)}`}
              className="text-base font-bold text-foreground hover:text-primary transition-colors truncate"
            >
              {result.title}
            </Link>
            {result.is_riverse && <RiverseBadge />}
          </div>
          {result.title_kr && (
            <p className="text-xs text-muted-foreground mt-0.5 truncate">{result.title_kr}</p>
          )}

          {/* 크로스 플랫폼 랭킹 */}
          <div className="flex flex-wrap gap-2 mt-2">
            {result.platforms.map((p) => {
              const platformInfo = getPlatformById(p.platform);
              return (
                <Link
                  key={p.platform}
                  href={`/title/${p.platform}/${encodeURIComponent(result.title)}`}
                  className="flex items-center gap-1.5 text-xs bg-muted px-2.5 py-1 rounded-full hover:bg-muted/80 transition-colors"
                >
                  <span
                    className="inline-block w-2 h-2 rounded-full"
                    style={{ backgroundColor: platformInfo?.color || "#888" }}
                  />
                  <span className="font-medium">{platformInfo?.name || p.platform}</span>
                  <span className="font-bold" style={{ color: platformInfo?.color || "#888" }}>
                    {p.rank}위
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
