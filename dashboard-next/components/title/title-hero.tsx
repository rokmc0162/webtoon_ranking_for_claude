"use client";

import { useState } from "react";
import { RiverseBadge } from "@/components/riverse-badge";
import type { TitleDetailMetadata } from "@/lib/types";

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

function formatDate(raw: string | null): string {
  if (!raw) return "";
  return raw.split("T")[0]; // "2026-02-17T00:00:00.000Z" → "2026-02-17"
}

interface TitleHeroProps {
  metadata: TitleDetailMetadata;
  platformColor: string;
  platformName: string;
}

export function TitleHero({ metadata, platformColor, platformName }: TitleHeroProps) {
  // 항상 프록시를 우선 사용 (외부 CDN CORS/referrer 문제 방지)
  const proxyUrl = `/api/thumbnail?platform=${encodeURIComponent(metadata.platform)}&title=${encodeURIComponent(metadata.title)}`;
  const hasThumbnail = !!(metadata.thumbnail_base64 || metadata.thumbnail_url);
  const [loadState, setLoadState] = useState<"proxy" | "cdn" | "fallback">(
    hasThumbnail ? "proxy" : "fallback"
  );
  const [descExpanded, setDescExpanded] = useState(false);

  let thumbnailSrc: string | null = null;
  if (loadState === "proxy") {
    thumbnailSrc = proxyUrl;
  } else if (loadState === "cdn" && metadata.thumbnail_url) {
    thumbnailSrc = metadata.thumbnail_url;
  }

  const tags = metadata.tags ? parseTags(metadata.tags) : [];
  const hasDescription = metadata.description && metadata.description.length > 0;
  const descriptionLong = hasDescription && metadata.description.length > 120;

  const firstDate = formatDate(metadata.first_seen_date);
  const lastDate = formatDate(metadata.last_seen_date);

  return (
    <div className="bg-card rounded-xl border p-4 sm:p-6">
      <div className="flex gap-4 sm:gap-6">
        {/* 썸네일 (3단 폴백: base64/CDN → proxy → emoji) */}
        <div className="shrink-0">
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
        </div>

        {/* 작품 정보 */}
        <div className="flex-1 min-w-0">
          {/* 타이틀 */}
          <h1 className="text-lg sm:text-xl font-bold text-foreground leading-tight">
            {metadata.title}
            {metadata.is_riverse && <RiverseBadge />}
          </h1>
          {metadata.title_kr && (
            <p className="text-sm text-muted-foreground mt-0.5">{metadata.title_kr}</p>
          )}

          {/* 메타 정보 라인 */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2 text-sm text-muted-foreground">
            <span
              className="font-medium px-2 py-0.5 rounded-full text-xs text-white"
              style={{ backgroundColor: platformColor }}
            >
              {platformName}
            </span>
            {metadata.author && <span>✍️ {metadata.author}</span>}
            {metadata.publisher && <span>📚 {metadata.publisher}</span>}
            {metadata.label && <span>🏷️ {metadata.label}</span>}
            {(metadata.genre_kr || metadata.genre) && (
              <span className="bg-muted px-2 py-0.5 rounded-full text-xs">
                {metadata.genre_kr || metadata.genre}
              </span>
            )}
          </div>

          {/* 핵심 수치 */}
          <div className="flex flex-wrap items-center gap-3 mt-3 text-sm">
            {metadata.best_rank != null && (
              <span className="font-medium">
                🏆 최고 <span className="font-bold" style={{ color: platformColor }}>{metadata.best_rank}위</span>
              </span>
            )}
            {firstDate && (
              <span className="text-muted-foreground text-xs">
                📅 {firstDate} ~ {lastDate}
              </span>
            )}
          </div>

          {/* 태그 */}
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {tags.map((tag) => (
                <span
                  key={tag}
                  className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded-full"
                >
                  #{tag}
                </span>
              ))}
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

      {/* 원본 링크 */}
      {metadata.url && (
        <div className="mt-3">
          <a
            href={metadata.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            🔗 {platformName}에서 보기 →
          </a>
        </div>
      )}
    </div>
  );
}
