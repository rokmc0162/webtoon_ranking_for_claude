"use client";

import { useState } from "react";
import Link from "next/link";
import { getPlatformById } from "@/lib/constants";
import type { TrendReport } from "@/lib/trend-report";

// ─── 리버스 브랜드 컬러 ────────────────────────────────
const RV = "#0D3B70";       // 리버스 로고 네이비
const RV_LIGHT = "#E8EEF5"; // 배경용 연한 톤
const RV_MID = "#1A5296";   // 호버/보조

// ─── Helper Components ────────────────────────────────

function PlatformBadge({ platform }: { platform: string }) {
  const info = getPlatformById(platform);
  const color = info?.color ?? "#666";
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold text-white shrink-0"
      style={{ backgroundColor: color }}
    >
      {info?.name ?? platform}
    </span>
  );
}

function RankBadge({ rank }: { rank: number }) {
  const bg =
    rank === 1
      ? "bg-yellow-400 text-yellow-900"
      : rank === 2
        ? "bg-gray-300 text-gray-800"
        : rank === 3
          ? "bg-amber-600 text-white"
          : "bg-muted text-muted-foreground";
  return (
    <span
      className={`inline-flex items-center justify-center w-7 h-5 rounded text-[11px] font-bold shrink-0 ${bg}`}
    >
      {rank}
    </span>
  );
}

function RankChange({ change }: { change: number }) {
  if (change > 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-emerald-500 font-bold text-xs">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
          <path d="M5 1L9 6H1L5 1Z" />
        </svg>
        {change}
      </span>
    );
  }
  if (change < 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-red-500 font-bold text-xs">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
          <path d="M5 9L1 4H9L5 9Z" />
        </svg>
        {Math.abs(change)}
      </span>
    );
  }
  return <span className="text-muted-foreground text-xs">-</span>;
}

function WorkLink({
  unifiedWorkId,
  children,
}: {
  unifiedWorkId: number | null;
  children: React.ReactNode;
}) {
  if (unifiedWorkId) {
    return (
      <Link
        href={`/work/${unifiedWorkId}`}
        className="hover:underline hover:text-primary transition-colors"
      >
        {children}
      </Link>
    );
  }
  return <>{children}</>;
}

function ShareBar({ pct }: { pct: number }) {
  return (
    <div className="flex items-center gap-2 flex-1">
      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: RV }}
        />
      </div>
      <span className="text-xs text-muted-foreground w-10 text-right font-mono">
        {pct}%
      </span>
    </div>
  );
}

function SectionTitle({ icon, children }: { icon: string; children: React.ReactNode }) {
  return (
    <h4 className="flex items-center gap-1.5 text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2 mt-0.5">
      <span>{icon}</span>
      {children}
    </h4>
  );
}

function ToggleButton({ open, onClick }: { open: boolean; onClick: () => void }) {
  return (
    <div className="px-4 py-2">
      <button
        onClick={onClick}
        className="group flex items-center gap-1.5 text-xs font-medium transition-colors cursor-pointer"
        style={{ color: RV_MID }}
      >
        <span
          className="inline-flex items-center justify-center w-5 h-5 rounded-full transition-colors"
          style={{ backgroundColor: RV_LIGHT }}
        >
          <svg
            width="10"
            height="10"
            viewBox="0 0 10 10"
            className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          >
            <path d="M1 3.5L5 7.5L9 3.5" stroke={RV_MID} strokeWidth="1.5" fill="none" strokeLinecap="round" />
          </svg>
        </span>
        {open ? "상세 데이터 접기" : "상세 데이터 보기"}
      </button>
    </div>
  );
}

function RvTag() {
  return (
    <span
      className="text-[9px] px-1 py-0.5 rounded font-semibold shrink-0"
      style={{ backgroundColor: RV_LIGHT, color: RV }}
    >
      RV
    </span>
  );
}

// ─── Riverse Card ────────────────────────────────

function RiverseCard({ report }: { report: TrendReport }) {
  const [open, setOpen] = useState(false);
  const { riverse } = report;

  return (
    <div
      className="relative overflow-hidden rounded-xl bg-card"
      style={{ border: `1px solid ${RV}22` }}
    >
      {/* Header — 리버스 네이비 배경, 흰 글씨 */}
      <div className="px-4 py-3" style={{ backgroundColor: RV }}>
        <h3 className="text-white font-bold text-sm tracking-wide">
          리버스 작품 동향
        </h3>
      </div>

      {/* Narrative Summary */}
      <div className="px-4 py-3" style={{ borderBottom: `1px solid ${RV}15` }}>
        <p className="text-[13px] text-foreground/85 leading-6 whitespace-pre-line">
          {riverse.summary || "데이터를 분석 중입니다..."}
        </p>
      </div>

      {/* Toggle */}
      <ToggleButton open={open} onClick={() => setOpen(!open)} />

      {/* Expandable Detail */}
      {open && (
        <div
          className="px-4 pb-4 space-y-4 pt-3 animate-in fade-in slide-in-from-top-2 duration-200"
          style={{ borderTop: `1px solid ${RV}15` }}
        >
          {/* TOP Ranked */}
          {riverse.top_ranked.length > 0 && (
            <div>
              <SectionTitle icon="🏆">리버스 TOP 랭킹</SectionTitle>
              <div className="space-y-1">
                {riverse.top_ranked.map((w, i) => (
                  <div key={`rv-top-${i}`} className="flex items-center gap-2 text-sm py-0.5">
                    <RankBadge rank={w.rank} />
                    <WorkLink unifiedWorkId={w.unified_work_id}>
                      <span className="font-medium truncate">{w.title}</span>
                    </WorkLink>
                    <PlatformBadge platform={w.platform} />
                    <RankChange change={w.rank_change} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Rising */}
          {riverse.rising.length > 0 && (
            <div>
              <SectionTitle icon="🚀">급상승 작품</SectionTitle>
              <div className="space-y-1">
                {riverse.rising.map((w, i) => (
                  <div key={`rv-rise-${i}`} className="flex items-center gap-2 text-sm py-0.5">
                    <WorkLink unifiedWorkId={w.unified_work_id}>
                      <span className="font-medium truncate">{w.title}</span>
                    </WorkLink>
                    <span className="text-muted-foreground text-xs shrink-0 font-mono">
                      {w.prev_rank}→{w.curr_rank}
                    </span>
                    <span className="text-emerald-500 font-bold text-xs shrink-0">+{w.change}</span>
                    <PlatformBadge platform={w.platform} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* New Entries */}
          {riverse.new_entries.length > 0 && (
            <div>
              <SectionTitle icon="🆕">신규 진입</SectionTitle>
              <div className="space-y-1">
                {riverse.new_entries.map((w, i) => (
                  <div key={`rv-new-${i}`} className="flex items-center gap-2 text-sm py-0.5">
                    <WorkLink unifiedWorkId={w.unified_work_id}>
                      <span className="font-medium truncate">{w.title}</span>
                    </WorkLink>
                    <PlatformBadge platform={w.platform} />
                    <span className="text-muted-foreground text-xs shrink-0 font-mono">#{w.rank}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Multi Platform */}
          {riverse.multi_platform.length > 0 && (
            <div>
              <SectionTitle icon="🌐">멀티플랫폼 인기작</SectionTitle>
              <div className="space-y-2">
                {riverse.multi_platform.map((w, i) => (
                  <div key={`rv-multi-${i}`} className="text-sm">
                    <div className="flex items-center gap-2 mb-0.5">
                      <WorkLink unifiedWorkId={w.unified_work_id}>
                        <span className="font-medium">{w.title}</span>
                      </WorkLink>
                      <span className="text-muted-foreground text-xs">({w.platform_count}개 플랫폼)</span>
                    </div>
                    <div className="flex flex-wrap gap-1 ml-2">
                      {w.platforms.map((p) => (
                        <span key={p.platform} className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
                          <PlatformBadge platform={p.platform} />
                          <span className="font-mono">#{p.rank}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Platform Share */}
          {riverse.platform_share.filter((p) => p.riverse_count > 0).length > 0 && (
            <div>
              <SectionTitle icon="📊">플랫폼별 리버스 점유율</SectionTitle>
              <div className="space-y-1.5">
                {riverse.platform_share
                  .filter((p) => p.riverse_count > 0)
                  .map((p) => (
                    <div key={p.platform} className="flex items-center gap-2 text-sm">
                      <span className="w-16 shrink-0 truncate text-xs font-medium">{p.platform_name}</span>
                      <span className="text-muted-foreground text-xs w-12 shrink-0 font-mono">
                        {p.riverse_count}/{p.total_ranked}
                      </span>
                      <ShareBar pct={p.share_pct} />
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Market Card ────────────────────────────────

function MarketCard({ report }: { report: TrendReport }) {
  const [open, setOpen] = useState(false);
  const { market } = report;

  return (
    <div
      className="relative overflow-hidden rounded-xl bg-card"
      style={{ border: `1px solid ${RV}22` }}
    >
      {/* Header — 흰 배경, 리버스 네이비 글씨 */}
      <div
        className="px-4 py-3 bg-white dark:bg-card"
        style={{ borderBottom: `2px solid ${RV}` }}
      >
        <h3 className="font-bold text-sm tracking-wide" style={{ color: RV }}>
          타사 · 시장 전체 동향
        </h3>
      </div>

      {/* Narrative Summary */}
      <div className="px-4 py-3" style={{ borderBottom: `1px solid ${RV}15` }}>
        <p className="text-[13px] text-foreground/85 leading-6 whitespace-pre-line">
          {market.summary || "데이터를 분석 중입니다..."}
        </p>
      </div>

      {/* Toggle */}
      <ToggleButton open={open} onClick={() => setOpen(!open)} />

      {/* Expandable Detail */}
      {open && (
        <div
          className="px-4 pb-4 space-y-4 pt-3 animate-in fade-in slide-in-from-top-2 duration-200"
          style={{ borderTop: `1px solid ${RV}15` }}
        >
          {/* Top 1 Per Platform */}
          {market.top1_works.length > 0 && (
            <div>
              <SectionTitle icon="👑">플랫폼별 1위</SectionTitle>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                {market.top1_works.map((w, i) => (
                  <div key={`mk-top1-${i}`} className="flex items-center gap-2 text-sm py-1 px-2 rounded-lg bg-muted/40">
                    <PlatformBadge platform={w.platform} />
                    <WorkLink unifiedWorkId={w.unified_work_id}>
                      <span className="font-medium truncate text-xs">{w.title}</span>
                    </WorkLink>
                    {w.is_riverse && <RvTag />}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Rising */}
          {market.top_rising.length > 0 && (
            <div>
              <SectionTitle icon="🚀">급상승 TOP</SectionTitle>
              <div className="space-y-1">
                {market.top_rising.map((w, i) => (
                  <div key={`mk-rise-${i}`} className="flex items-center gap-2 text-sm py-0.5">
                    <WorkLink unifiedWorkId={w.unified_work_id}>
                      <span className="font-medium truncate">{w.title}</span>
                    </WorkLink>
                    <span className="text-muted-foreground text-xs shrink-0 font-mono">
                      {w.prev_rank}→{w.curr_rank}
                    </span>
                    <span className="text-emerald-500 font-bold text-xs shrink-0">+{w.change}</span>
                    <PlatformBadge platform={w.platform} />
                    {w.is_riverse && <RvTag />}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* New Entries */}
          {market.new_entries.length > 0 && (
            <div>
              <SectionTitle icon="🆕">신규 진입</SectionTitle>
              <div className="space-y-1">
                {market.new_entries.map((w, i) => (
                  <div key={`mk-new-${i}`} className="flex items-center gap-2 text-sm py-0.5">
                    <WorkLink unifiedWorkId={w.unified_work_id}>
                      <span className="font-medium truncate">{w.title}</span>
                    </WorkLink>
                    <PlatformBadge platform={w.platform} />
                    <span className="text-muted-foreground text-xs shrink-0 font-mono">#{w.rank}</span>
                    {w.is_riverse && <RvTag />}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Multi Platform (non-riverse) */}
          {market.multi_platform.length > 0 && (
            <div>
              <SectionTitle icon="🌐">타사 멀티플랫폼 히트</SectionTitle>
              <div className="space-y-2">
                {market.multi_platform.map((w, i) => (
                  <div key={`mk-multi-${i}`} className="text-sm">
                    <div className="flex items-center gap-2 mb-0.5">
                      <WorkLink unifiedWorkId={w.unified_work_id}>
                        <span className="font-medium">{w.title}</span>
                      </WorkLink>
                      <span className="text-muted-foreground text-xs">({w.platform_count}개 플랫폼)</span>
                    </div>
                    <div className="flex flex-wrap gap-1 ml-2">
                      {w.platforms.map((p) => (
                        <span key={p.platform} className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
                          <PlatformBadge platform={p.platform} />
                          <span className="font-mono">#{p.rank}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Export ────────────────────────────────

export function TrendReportCard({ report }: { report?: TrendReport | null }) {
  if (!report) return null;

  return (
    <div className="space-y-3">
      {/* Section Header */}
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-bold text-foreground flex items-center gap-1.5">
          <span>📊</span>
          JP 웹툰 트렌드 리포트
        </h2>
        <span className="text-[11px] text-muted-foreground">
          {report.data_date} vs {report.prev_date}
        </span>
      </div>

      {/* Two cards side by side on desktop, stacked on mobile */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <RiverseCard report={report} />
        <MarketCard report={report} />
      </div>
    </div>
  );
}
