"use client";

import { type ReactElement, useState, useEffect } from "react";

const RV = "#0D3B70";

interface UnifiedAiAnalysisProps {
  workId: number;
}

export function UnifiedAiAnalysis({ workId }: UnifiedAiAnalysisProps) {
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState("");

  // 마운트 시 캐시된 분석만 확인 (자동 생성하지 않음)
  useEffect(() => {
    fetch(`/api/work-analysis?id=${workId}&cache_only=true`)
      .then((res) => {
        if (!res.ok) return null;
        return res.json();
      })
      .then((data) => {
        if (data?.analysis) {
          setAnalysis(data.analysis);
          setGeneratedAt(data.generated_at || null);
        }
        setInitialLoading(false);
      })
      .catch(() => {
        setInitialLoading(false);
      });
  }, [workId]);

  const handleAnalyze = (refresh: boolean) => {
    setLoading(true);
    setError("");

    const url = refresh
      ? `/api/work-analysis?id=${workId}&refresh=true`
      : `/api/work-analysis?id=${workId}`;

    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error("분석 실패");
        return res.json();
      })
      .then((data) => {
        setAnalysis(data.analysis);
        setGeneratedAt(data.generated_at || null);
        setLoading(false);
      })
      .catch(() => {
        setError("분석을 생성할 수 없습니다.");
        setLoading(false);
      });
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`;
  };

  const renderAnalysis = (text: string) => {
    // "1. 시장 포지션" 이전의 서론/과정 설명 제거
    const sectionStart = text.indexOf("1.");
    const trimmed = sectionStart > 0 ? text.slice(sectionStart) : text;

    const cleaned = trimmed
      .replace(/#{1,4}\s*/g, "")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/\*([^*]+)\*/g, "$1")
      .replace(/^[-•]\s+/gm, "")
      .replace(/\(웹\)/g, "")
      .replace(/\(DB\)/g, "")
      .replace(/\(웹 검색 기반\)/g, "");

    // 섹션 단위로 파싱
    const sections: { title: string; paragraphs: string[] }[] = [];
    let currentSection: { title: string; paragraphs: string[] } | null = null;
    let currentParagraph: string[] = [];

    const flushParagraph = () => {
      if (currentParagraph.length > 0 && currentSection) {
        currentSection.paragraphs.push(currentParagraph.join(" "));
        currentParagraph = [];
      }
    };

    for (const line of cleaned.split("\n")) {
      const trimLine = line.trim();
      if (/^\d+\.\s+.+/.test(trimLine) && trimLine.length < 40) {
        flushParagraph();
        if (currentSection) sections.push(currentSection);
        currentSection = { title: trimLine, paragraphs: [] };
      } else if (trimLine === "") {
        flushParagraph();
      } else if (currentSection) {
        currentParagraph.push(trimLine);
      }
    }
    flushParagraph();
    if (currentSection) sections.push(currentSection);

    return sections.map((section, si) => (
      <div key={si} className={si > 0 ? "mt-7" : ""}>
        <div
          className="text-[13px] font-bold tracking-tight mb-3 pb-2 border-b"
          style={{ color: RV, borderColor: `${RV}20` }}
        >
          {section.title}
        </div>
        <div className="space-y-2.5">
          {section.paragraphs.map((p, pi) => (
            <p
              key={pi}
              className="text-[13.5px] text-foreground/85 leading-[1.9] tracking-tight"
            >
              {p}
            </p>
          ))}
        </div>
      </div>
    ));
  };

  return (
    <div className="bg-card rounded-xl border p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-bold">작품 분석</h2>
        {!analysis && !loading && !initialLoading && (
          <button
            onClick={() => handleAnalyze(false)}
            className="px-4 py-1.5 text-sm font-medium rounded-full text-white transition-opacity hover:opacity-90 cursor-pointer"
            style={{ backgroundColor: RV }}
          >
            분석 시작
          </button>
        )}
      </div>

      {initialLoading && (
        <div className="text-center py-6">
          <div
            className="inline-block w-5 h-5 border-2 border-t-transparent rounded-full animate-spin"
            style={{ borderColor: RV, borderTopColor: "transparent" }}
          />
        </div>
      )}

      {!analysis && !loading && !initialLoading && !error && (
        <p className="text-sm text-muted-foreground text-center py-6">
          랭킹, 리뷰, 시장 데이터를 종합한 전문 분석을 제공합니다.
        </p>
      )}

      {loading && (
        <div className="text-center py-8">
          <div
            className="inline-block w-6 h-6 border-2 border-t-transparent rounded-full animate-spin mb-2"
            style={{ borderColor: RV, borderTopColor: "transparent" }}
          />
          <p className="text-sm text-muted-foreground">데이터를 분석하고 있습니다...</p>
        </div>
      )}

      {error && (
        <div className="text-center py-6">
          <p className="text-sm text-red-500 mb-2">{error}</p>
          <button
            onClick={() => handleAnalyze(false)}
            className="text-xs hover:underline cursor-pointer"
            style={{ color: RV }}
          >
            다시 시도
          </button>
        </div>
      )}

      {analysis && !loading && (
        <div>
          {renderAnalysis(analysis)}
          <div className="mt-5 pt-3 border-t text-xs text-muted-foreground flex items-center justify-between">
            <span>
              {generatedAt ? `분석일 ${formatDate(generatedAt)}` : ""}
            </span>
            <button
              onClick={() => handleAnalyze(true)}
              className="hover:underline cursor-pointer"
              style={{ color: RV }}
            >
              재분석
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
