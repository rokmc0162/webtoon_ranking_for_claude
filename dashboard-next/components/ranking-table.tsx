"use client";

import { useState } from "react";
import Link from "next/link";
import { RankBadge } from "./rank-badge";
import { RankChange } from "./rank-change";
import { RiverseBadge } from "./riverse-badge";
import type { Ranking } from "@/lib/types";

interface RankingTableProps {
  rankings: Ranking[];
  platformColor: string;
  platform: string;
}

function Thumbnail({
  ranking,
  platform,
}: {
  ranking: Ranking;
  platform: string;
}) {
  const [loadState, setLoadState] = useState<"cdn" | "proxy" | "fallback">(
    "cdn"
  );

  const cdnUrl = ranking.thumbnail_url;
  const proxyUrl = `/api/thumbnail?platform=${encodeURIComponent(platform)}&title=${encodeURIComponent(ranking.title)}`;

  if (!cdnUrl || loadState === "fallback") {
    return (
      <div className="w-[44px] h-[62px] bg-muted rounded flex items-center justify-center text-lg shrink-0">
        📖
      </div>
    );
  }

  const src = loadState === "cdn" ? cdnUrl : proxyUrl;

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt=""
      width={44}
      height={62}
      className="rounded shadow-sm bg-muted shrink-0"
      style={{ width: 44, height: 62, objectFit: "cover" }}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => {
        if (loadState === "cdn") {
          setLoadState("proxy");
        } else {
          setLoadState("fallback");
        }
      }}
    />
  );
}

export function RankingTable({
  rankings,
  platformColor,
  platform,
}: RankingTableProps) {
  if (rankings.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        데이터가 없습니다.
      </div>
    );
  }

  return (
    <div className="w-full">
      <table
        className="w-full text-sm border-collapse"
        style={{ tableLayout: "fixed" }}
      >
        <thead>
          <tr className="bg-muted/50 border-b">
            <th
              style={{ width: 50 }}
              className="h-10 px-2 text-center font-medium text-foreground"
            >
              순위
            </th>
            <th
              style={{ width: 56 }}
              className="h-10 px-1 font-medium"
            ></th>
            <th
              style={{ width: 60 }}
              className="h-10 px-2 text-center font-medium text-foreground"
            >
              변동
            </th>
            <th className="h-10 px-2 text-left font-medium text-foreground">
              작품명
            </th>
            <th
              style={{ width: 180 }}
              className="h-10 px-2 text-left font-medium text-foreground hidden md:table-cell"
            >
              한국어
            </th>
            <th
              style={{ width: 100 }}
              className="h-10 px-2 text-left font-medium text-foreground hidden md:table-cell"
            >
              장르
            </th>
            <th
              style={{ width: 56 }}
              className="h-10 px-2 text-center font-medium text-foreground"
            >
              분석
            </th>
          </tr>
        </thead>
        <tbody>
          {rankings.map((r) => (
            <tr
              key={r.rank}
              className="border-b hover:bg-muted/30 transition-colors"
            >
              {/* 순위 */}
              <td className="py-2 px-2 text-center align-middle">
                <RankBadge rank={r.rank} platformColor={platformColor} />
              </td>

              {/* 썸네일 */}
              <td className="py-2 px-1 align-middle">
                <Thumbnail ranking={r} platform={platform} />
              </td>

              {/* 변동 */}
              <td className="py-2 px-2 text-center align-middle">
                <RankChange change={r.rank_change} />
              </td>

              {/* 작품명 */}
              <td className="py-2 px-2 align-middle overflow-hidden">
                <div className="truncate">
                  <Link
                    href={r.unified_work_id ? `/work/${r.unified_work_id}` : `/title/${platform}/${encodeURIComponent(r.title)}`}
                    target="_blank"
                    className="font-medium text-foreground hover:underline"
                    style={{ textDecorationColor: platformColor }}
                  >
                    {r.title}
                  </Link>
                  {r.is_riverse && <RiverseBadge />}
                  {r.url && (
                    <a
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-1 text-xs text-muted-foreground hover:text-foreground"
                      title="원본 페이지"
                    >
                      🔗
                    </a>
                  )}
                </div>
                {/* 모바일: 한국어 제목 + 장르 인라인 */}
                <div className="md:hidden mt-0.5 truncate">
                  {r.title_kr && (
                    <span className="text-xs text-muted-foreground">
                      {r.title_kr}
                    </span>
                  )}
                  {(r.genre_kr || r.genre) && (
                    <span className="ml-2 text-[10px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded-full">
                      {r.genre_kr || r.genre}
                    </span>
                  )}
                </div>
              </td>

              {/* 한국어 */}
              <td className="py-2 px-2 align-middle text-muted-foreground text-sm hidden md:table-cell overflow-hidden">
                <div className="truncate">{r.title_kr || ""}</div>
              </td>

              {/* 장르 */}
              <td className="py-2 px-2 align-middle hidden md:table-cell">
                {(r.genre_kr || r.genre) && (
                  <span className="bg-muted text-muted-foreground px-2 py-0.5 rounded-full text-xs whitespace-nowrap">
                    {r.genre_kr || r.genre}
                  </span>
                )}
              </td>

              {/* 분석 페이지 링크 */}
              <td className="py-2 px-2 text-center align-middle">
                <Link
                  href={r.unified_work_id ? `/work/${r.unified_work_id}` : `/title/${platform}/${encodeURIComponent(r.title)}`}
                  target="_blank"
                  className="text-xl opacity-60 hover:opacity-100 transition-opacity"
                  title="작품 상세 분석"
                >
                  📊
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
