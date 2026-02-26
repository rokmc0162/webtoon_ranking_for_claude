"use client";

import { useState } from "react";
import { RiverseBadge } from "@/components/riverse-badge";
import { isJapanesePlatform } from "@/lib/constants";
import type { UnifiedWorkMetadata, PlatformWorkEntry } from "@/lib/types";

function parseTags(raw: string): string[] {
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return [...new Set(parsed.map((t: string) => t.trim()).filter(Boolean))];
    }
  } catch {
    // not JSON
  }
  return [...new Set(raw.split(",").map((t) => t.trim()).filter(Boolean))];
}

interface UnifiedHeroProps {
  metadata: UnifiedWorkMetadata;
  platforms: PlatformWorkEntry[];
}

export function UnifiedHero({ metadata, platforms }: UnifiedHeroProps) {
  // 썸네일: 일본 플랫폼 우선
  const jpPlatforms = platforms.filter((p) => isJapanesePlatform(p.platform));
  const enPlatforms = platforms.filter((p) => !isJapanesePlatform(p.platform));
  const primaryPlatform = jpPlatforms[0] || platforms[0];
  const proxyUrl = primaryPlatform
    ? `/api/thumbnail?platform=${encodeURIComponent(primaryPlatform.platform)}&title=${encodeURIComponent(primaryPlatform.title)}`
    : null;
  // 영어 플랫폼 썸네일 (일본 버전과 다른 경우에만 표시)
  const enThumbPlatform = enPlatforms[0];
  const enProxyUrl = enThumbPlatform
    ? `/api/thumbnail?platform=${encodeURIComponent(enThumbPlatform.platform)}&title=${encodeURIComponent(enThumbPlatform.title)}`
    : null;
  const showEnThumb = enProxyUrl && enThumbPlatform && jpPlatforms.length > 0;

  const hasThumbnail = !!(metadata.thumbnail_url);
  const [loadState, setLoadState] = useState<"proxy" | "cdn" | "fallback">(
    hasThumbnail && proxyUrl ? "proxy" : "fallback"
  );
  const [enThumbError, setEnThumbError] = useState(false);
  const [descExpanded, setDescExpanded] = useState(false);

  let thumbnailSrc: string | null = null;
  if (loadState === "proxy" && proxyUrl) {
    thumbnailSrc = proxyUrl;
  } else if (loadState === "cdn" && metadata.thumbnail_url) {
    thumbnailSrc = metadata.thumbnail_url;
  }

  const tags = metadata.tags ? parseTags(metadata.tags) : [];
  const hasDescription = metadata.description && metadata.description.length > 0;
  const descriptionLong = hasDescription && metadata.description.length > 120;

  // 최고 순위 (전 플랫폼 통합)
  const bestRank = platforms
    .map((p) => p.best_rank)
    .filter((r): r is number => r !== null);
  const overallBest = bestRank.length > 0 ? Math.min(...bestRank) : null;

  return (
    <div className="bg-card rounded-xl border p-4 sm:p-6">
      <div className="flex gap-4 sm:gap-6">
        {/* 썸네일 */}
        <div className="shrink-0 flex gap-2">
          {/* 메인 썸네일 (일본어 버전 우선) */}
          {thumbnailSrc ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={thumbnailSrc}
              alt=""
              width={100}
              height={140}
              className="rounded-lg shadow-md bg-muted"
              style={{ width: 100, height: 140, objectFit: "cover" }}
              referrerPolicy="no-referrer"
              onError={() => {
                if (loadState === "proxy") setLoadState("cdn");
                else setLoadState("fallback");
              }}
            />
          ) : (
            <div className="w-[100px] h-[140px] bg-muted rounded-lg flex items-center justify-center text-3xl">
              📖
            </div>
          )}
          {/* 영어 플랫폼 썸네일 (별도 표시) */}
          {showEnThumb && !enThumbError && (
            <div className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={enProxyUrl!}
                alt=""
                width={72}
                height={100}
                className="rounded-lg bg-muted border border-border"
                style={{ width: 72, height: 100, objectFit: "cover" }}
                referrerPolicy="no-referrer"
                onError={() => setEnThumbError(true)}
              />
              <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 text-[10px] bg-background/90 text-muted-foreground px-1.5 py-0.5 rounded-full border whitespace-nowrap">
                🇬🇧 EN
              </span>
            </div>
          )}
        </div>

        {/* 작품 정보 */}
        <div className="flex-1 min-w-0">
          {/* 타이틀 */}
          <h1 className="text-lg sm:text-xl font-bold text-foreground leading-tight">
            {metadata.title_kr}
            {metadata.is_riverse && <RiverseBadge />}
          </h1>
          {metadata.title_en && metadata.title_en !== metadata.title_kr && (
            <p className="text-sm text-muted-foreground mt-0.5">{metadata.title_en}</p>
          )}
          {metadata.title_canonical && metadata.title_canonical !== metadata.title_kr
            && metadata.title_canonical !== metadata.title_en && (
            <p className="text-sm text-muted-foreground mt-0.5">{metadata.title_canonical}</p>
          )}

          {/* 플랫폼 배지들 */}
          <div className="flex flex-wrap items-center gap-1.5 mt-2">
            {platforms.map((p) => (
              <a
                key={p.platform}
                href={p.url || "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium px-2 py-0.5 rounded-full text-xs text-white hover:opacity-80 transition-opacity"
                style={{ backgroundColor: p.platform_color }}
                title={`${p.platform_name}에서 보기`}
              >
                {p.platform_name}
              </a>
            ))}
          </div>

          {/* 메타 정보 라인 */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2 text-sm text-muted-foreground">
            {metadata.author && <span>✍️ {metadata.author}</span>}
            {metadata.publisher && <span>📚 {metadata.publisher}</span>}
            {(metadata.genre_kr || metadata.genre) && (
              <span className="bg-muted px-2 py-0.5 rounded-full text-xs">
                {metadata.genre_kr || metadata.genre}
              </span>
            )}
          </div>

          {/* 핵심 수치 */}
          <div className="flex flex-wrap items-center gap-3 mt-3 text-sm">
            {overallBest != null && (
              <span className="font-medium">
                🏆 최고 <span className="font-bold text-blue-600">{overallBest}위</span>
              </span>
            )}
            <span className="text-muted-foreground text-xs">
              📡 {platforms.length}개 플랫폼
            </span>
          </div>

          {/* 태그 */}
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {tags.slice(0, 15).map((tag) => (
                <span
                  key={tag}
                  className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded-full"
                >
                  #{tag}
                </span>
              ))}
              {tags.length > 15 && (
                <span className="text-xs text-muted-foreground">+{tags.length - 15}</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 설명 */}
      {hasDescription && (
        <div className="mt-4 text-sm text-foreground/80 leading-relaxed">
          {descriptionLong && !descExpanded ? (
            <>
              {metadata.description.slice(0, 120)}...
              <button
                onClick={() => setDescExpanded(true)}
                className="ml-1 text-xs text-blue-500 hover:underline cursor-pointer"
              >
                더보기
              </button>
            </>
          ) : (
            <>
              {metadata.description}
              {descriptionLong && (
                <button
                  onClick={() => setDescExpanded(false)}
                  className="ml-1 text-xs text-blue-500 hover:underline cursor-pointer"
                >
                  접기
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
