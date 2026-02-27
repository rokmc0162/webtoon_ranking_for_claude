"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Header } from "@/components/header";
import { DateSelector } from "@/components/date-selector";
import { PlatformTabs } from "@/components/platform-tabs";
import { GenrePills } from "@/components/genre-pills";
import { RankingTable } from "@/components/ranking-table";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { getPlatformById } from "@/lib/constants";
import { staggerContainer, fadeSlideUp, contentSwap } from "@/lib/motion";
import type { Ranking, PlatformStats } from "@/lib/types";
import type { TrendReport } from "@/lib/trend-report";
import { TrendReportCard } from "@/components/trend-report";

interface DashboardClientProps {
  initialDates: string[];
  initialDate: string;
  initialStats: Record<string, PlatformStats>;
  initialRiverseCounts: Record<string, number>;
  initialRankings: Ranking[];
  initialPlatform: string;
  trendReport?: TrendReport | null;
}

export function DashboardClient({
  initialDates,
  initialDate,
  initialStats,
  initialRiverseCounts,
  initialRankings,
  initialPlatform,
  trendReport,
}: DashboardClientProps) {
  const [dates] = useState<string[]>(initialDates);
  const [selectedDate, setSelectedDate] = useState(initialDate);
  const [selectedPlatform, setSelectedPlatform] = useState(initialPlatform);
  const [selectedGenre, setSelectedGenre] = useState("");
  const [rankings, setRankings] = useState<Ranking[]>(initialRankings);
  const [stats, setStats] = useState<Record<string, PlatformStats>>(initialStats);
  const [riverseCounts, setRiverseCounts] = useState<Record<string, number>>(initialRiverseCounts);
  const [riverseOnly, setRiverseOnly] = useState(false);
  const [loading, setLoading] = useState(false); // 초기 false: 서버에서 이미 로드됨

  // 초기 상태 판별: 서버에서 미리 로드한 데이터를 재사용할 수 있는지 확인
  const isInitialState = selectedDate === initialDate && selectedPlatform === initialPlatform && selectedGenre === "";

  // 통계 로드 (날짜 변경 시)
  useEffect(() => {
    if (selectedDate === initialDate) {
      // 초기 날짜로 돌아온 경우 서버 데이터 복원
      setStats(initialStats);
      return;
    }
    fetch(`/api/stats?date=${selectedDate}`)
      .then((res) => res.json())
      .then(setStats);
  }, [selectedDate, initialDate, initialStats]);

  // 리버스 카운트 로드
  useEffect(() => {
    if (selectedDate === initialDate && selectedPlatform === initialPlatform) {
      // 초기 상태로 돌아온 경우 서버 데이터 복원
      setRiverseCounts(initialRiverseCounts);
      return;
    }
    fetch(`/api/riverse-counts?date=${selectedDate}&platform=${selectedPlatform}`)
      .then((res) => res.json())
      .then(setRiverseCounts);
  }, [selectedDate, selectedPlatform, initialDate, initialPlatform, initialRiverseCounts]);

  // 랭킹 로드
  useEffect(() => {
    if (isInitialState) {
      // 초기 상태로 돌아온 경우 서버 데이터 복원
      setRankings(initialRankings);
      setLoading(false);
      return;
    }
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
  }, [selectedDate, selectedPlatform, selectedGenre, isInitialState, initialRankings]);

  // 플랫폼 변경 시 장르를 해당 플랫폼의 첫 번째 장르로 설정
  const handlePlatformChange = (id: string) => {
    setSelectedPlatform(id);
    const pInfo = getPlatformById(id);
    const firstGenreKey = pInfo?.genres[0]?.key ?? "";
    setSelectedGenre(firstGenreKey);
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
    <motion.div
      className="min-h-screen bg-background"
      variants={staggerContainer}
      initial="hidden"
      animate="show"
    >
      <div className="max-w-[1200px] mx-auto px-3 sm:px-6">
        <motion.div variants={fadeSlideUp}>
          <Header />
        </motion.div>

        {/* 트렌드 리포트 */}
        <motion.div variants={fadeSlideUp} className="mt-4">
          <TrendReportCard report={trendReport} />
        </motion.div>

        {/* 날짜 + 출처 */}
        <motion.div variants={fadeSlideUp} className="flex items-center justify-between mt-4 mb-3">
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
        </motion.div>

        {/* 플랫폼 탭 */}
        <motion.div variants={fadeSlideUp}>
          <PlatformTabs
            selected={selectedPlatform}
            onSelect={handlePlatformChange}
            stats={stats}
          />
        </motion.div>

        {/* 장르 필터 */}
        {platform && platform.genres.length > 1 && (
          <motion.div variants={fadeSlideUp} className="mt-3">
            <GenrePills
              genres={platform.genres}
              selected={selectedGenre}
              onSelect={setSelectedGenre}
              platformColor={platformColor}
              riverseCounts={riverseCounts}
            />
          </motion.div>
        )}

        {/* 필터 바 */}
        <motion.div variants={fadeSlideUp} className="flex items-center justify-between mt-4 mb-2">
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
        </motion.div>

        {/* 랭킹 테이블 */}
        <AnimatePresence mode="wait">
          {loading ? (
            <motion.div
              key="skeleton"
              variants={contentSwap}
              initial="enter"
              animate="center"
              exit="exit"
              className="space-y-3 mt-4"
            >
              {Array.from({ length: 10 }).map((_, i) => (
                <Skeleton key={i} className="h-[72px] w-full rounded-lg" />
              ))}
            </motion.div>
          ) : (
            <motion.div
              key={`table-${selectedPlatform}-${selectedGenre}`}
              variants={contentSwap}
              initial="enter"
              animate="center"
              exit="exit"
            >
              <RankingTable
                rankings={displayRankings}
                platformColor={platformColor}
                platform={selectedPlatform}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* 푸터 */}
        <Separator className="mt-8" />
        <footer className="py-4 text-center text-xs text-muted-foreground">
          RIVERSE Inc. | 데이터: Supabase PostgreSQL | 매일 자동 수집
        </footer>
      </div>
    </motion.div>
  );
}
