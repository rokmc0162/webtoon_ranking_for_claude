"use client";

import { useState, useEffect, useCallback } from "react";
import { Header } from "@/components/header";
import { DateSelector } from "@/components/date-selector";
import { PlatformTabs } from "@/components/platform-tabs";
import { GenrePills } from "@/components/genre-pills";
import { RankingTable } from "@/components/ranking-table";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { getPlatformById } from "@/lib/constants";
import type { Ranking, PlatformStats } from "@/lib/types";

export default function Home() {
  const [dates, setDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedPlatform, setSelectedPlatform] = useState("piccoma");
  const [selectedGenre, setSelectedGenre] = useState("");
  const [rankings, setRankings] = useState<Ranking[]>([]);
  const [stats, setStats] = useState<Record<string, PlatformStats>>({});
  const [riverseCounts, setRiverseCounts] = useState<Record<string, number>>({});
  const [riverseOnly, setRiverseOnly] = useState(false);
  const [loading, setLoading] = useState(true);

  // 초기 날짜 로드
  useEffect(() => {
    fetch("/api/dates")
      .then((res) => res.json())
      .then((data: string[]) => {
        setDates(data);
        if (data.length > 0) {
          setSelectedDate(data[0]);
        }
      });
  }, []);

  // 통계 로드
  useEffect(() => {
    if (!selectedDate) return;
    fetch(`/api/stats?date=${selectedDate}`)
      .then((res) => res.json())
      .then(setStats);
  }, [selectedDate]);

  // 리버스 카운트 로드
  useEffect(() => {
    if (!selectedDate || !selectedPlatform) return;
    fetch(
      `/api/riverse-counts?date=${selectedDate}&platform=${selectedPlatform}`
    )
      .then((res) => res.json())
      .then(setRiverseCounts);
  }, [selectedDate, selectedPlatform]);

  // 랭킹 로드
  const loadRankings = useCallback(() => {
    if (!selectedDate || !selectedPlatform) return;
    setLoading(true);
    const params = new URLSearchParams({
      date: selectedDate,
      platform: selectedPlatform,
      sub_category: selectedGenre,
    });
    fetch(`/api/rankings?${params}`)
      .then((res) => res.json())
      .then((data: Ranking[]) => {
        setRankings(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [selectedDate, selectedPlatform, selectedGenre]);

  useEffect(() => {
    loadRankings();
  }, [loadRankings]);

  // 플랫폼 변경 시 장르 리셋
  const handlePlatformChange = (id: string) => {
    setSelectedPlatform(id);
    setSelectedGenre("");
    setRiverseOnly(false);
  };

  const platform = getPlatformById(selectedPlatform);
  const platformColor = platform?.color || "#0D3B70";

  // 리버스 필터
  const displayRankings = riverseOnly
    ? rankings.filter((r) => r.is_riverse)
    : rankings;

  // 출처 링크
  const sourceUrl = platform?.sourceUrl || "";

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-[1200px] mx-auto px-3 sm:px-6">
        <Header />

        {/* 날짜 + 출처 */}
        <div className="flex items-center justify-between mt-4 mb-3">
          <DateSelector
            dates={dates}
            selected={selectedDate}
            onSelect={setSelectedDate}
          />
          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              📎 데이터 출처: {platform?.name}
            </a>
          )}
        </div>

        {/* 플랫폼 탭 */}
        <PlatformTabs
          selected={selectedPlatform}
          onSelect={handlePlatformChange}
          stats={stats}
        />

        {/* 장르 필터 */}
        {platform && platform.genres.length > 1 && (
          <div className="mt-3">
            <GenrePills
              genres={platform.genres}
              selected={selectedGenre}
              onSelect={setSelectedGenre}
              platformColor={platformColor}
              riverseCounts={riverseCounts}
            />
          </div>
        )}

        {/* 필터 바 */}
        <div className="flex items-center justify-between mt-4 mb-2">
          <div className="text-sm font-medium text-foreground">
            <span className="font-bold" style={{ color: platformColor }}>
              {platform?.name}
            </span>
            {selectedGenre && platform && (
              <span className="text-muted-foreground ml-1">
                [{platform.genres.find((g) => g.key === selectedGenre)?.label}]
              </span>
            )}
            <span className="text-muted-foreground ml-2">
              TOP {displayRankings.length} — {selectedDate}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="riverse-filter"
              checked={riverseOnly}
              onCheckedChange={(v) => setRiverseOnly(v === true)}
            />
            <label
              htmlFor="riverse-filter"
              className="text-sm text-muted-foreground cursor-pointer select-none"
            >
              리버스 작품만
            </label>
          </div>
        </div>

        {/* 랭킹 테이블 */}
        {loading ? (
          <div className="space-y-3 mt-4">
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton key={i} className="h-[72px] w-full rounded-lg" />
            ))}
          </div>
        ) : (
          <RankingTable
            rankings={displayRankings}
            platformColor={platformColor}
            platform={selectedPlatform}
          />
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
