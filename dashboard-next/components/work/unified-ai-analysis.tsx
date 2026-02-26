"use client";

import { type ReactElement, useState } from "react";

const RV = "#0D3B70";

interface UnifiedAiAnalysisProps {
  workId: number;
}

export function UnifiedAiAnalysis({ workId }: UnifiedAiAnalysisProps) {
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleAnalyze = () => {
    setLoading(true);
    setError("");
    setAnalysis(null);

    fetch(`/api/work-analysis?id=${workId}`)
      .then((res) => {
        if (!res.ok) throw new Error("분석 실패");
        return res.json();
      })
      .then((data) => {
        setAnalysis(data.analysis);
        setLoading(false);
      })
      .catch(() => {
        setError("분석을 생성할 수 없습니다.");
        setLoading(false);
      });
  };

  // 텍스트를 깔끔하게 렌더링 (마크다운 기호 제거)
  const renderAnalysis = (text: string) => {
    // 마크다운 잔재 정리
    const cleaned = text
      .replace(/#{1,4}\s*/g, "")       // # ## ### ####
      .replace(/\*\*([^*]+)\*\*/g, "$1") // **bold**
      .replace(/\*([^*]+)\*/g, "$1")     // *italic*
      .replace(/^[-•]\s+/gm, "");        // - bullet, • bullet

    const lines = cleaned.split("\n");
    const elements: ReactElement[] = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      // 섹션 제목: "1. 시장 포지션" 같은 패턴
      if (/^\d+\.\s+.+/.test(line) && line.length < 30) {
        elements.push(
          <h3
            key={i}
            className="text-[13px] font-bold mt-5 mb-2 tracking-tight"
            style={{ color: RV }}
          >
            {line}
          </h3>
        );
      } else if (line === "") {
        elements.push(<div key={i} className="h-2" />);
      } else {
        elements.push(
          <p key={i} className="text-[13px] text-foreground/85 leading-[1.8]">
            {line}
          </p>
        );
      }
    }

    return elements;
  };

  return (
    <div className="bg-card rounded-xl border p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-bold">작품 분석</h2>
        {!analysis && !loading && (
          <button
            onClick={handleAnalyze}
            className="px-4 py-1.5 text-sm font-medium rounded-full text-white transition-opacity hover:opacity-90 cursor-pointer"
            style={{ backgroundColor: RV }}
          >
            분석 시작
          </button>
        )}
      </div>

      {!analysis && !loading && !error && (
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
            onClick={handleAnalyze}
            className="text-xs hover:underline cursor-pointer"
            style={{ color: RV }}
          >
            다시 시도
          </button>
        </div>
      )}

      {analysis && (
        <div>
          {renderAnalysis(analysis)}
          <div className="mt-5 pt-3 border-t text-xs text-muted-foreground flex items-center justify-between">
            <span>수집 데이터 + 웹 검색 기반</span>
            <button
              onClick={handleAnalyze}
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
