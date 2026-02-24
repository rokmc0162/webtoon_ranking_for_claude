"use client";

import { type ReactElement, useState } from "react";

interface AiAnalysisProps {
  platform: string;
  title: string;
  platformColor: string;
}

export function AiAnalysis({ platform, title, platformColor }: AiAnalysisProps) {
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleAnalyze = () => {
    setLoading(true);
    setError("");
    setAnalysis(null);

    fetch(
      `/api/title-analysis?platform=${encodeURIComponent(platform)}&title=${encodeURIComponent(title)}`
    )
      .then((res) => {
        if (!res.ok) throw new Error("분석 실패");
        return res.json();
      })
      .then((data) => {
        setAnalysis(data.analysis);
        setLoading(false);
      })
      .catch(() => {
        setError("AI 분석을 생성할 수 없습니다. API 키를 확인해주세요.");
        setLoading(false);
      });
  };

  // 마크다운 헤딩을 간단히 파싱
  const renderAnalysis = (text: string) => {
    const lines = text.split("\n");
    const elements: ReactElement[] = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      if (line.startsWith("### ")) {
        elements.push(
          <h3
            key={i}
            className="text-sm font-bold mt-4 mb-1.5 flex items-center gap-1.5"
            style={{ color: platformColor }}
          >
            {line.replace("### ", "")}
          </h3>
        );
      } else if (line.startsWith("## ")) {
        elements.push(
          <h2 key={i} className="text-base font-bold mt-4 mb-2" style={{ color: platformColor }}>
            {line.replace("## ", "")}
          </h2>
        );
      } else if (line.startsWith("- ")) {
        elements.push(
          <li key={i} className="text-sm text-foreground/90 leading-relaxed ml-4 list-disc">
            {line.replace("- ", "")}
          </li>
        );
      } else if (line.trim() === "") {
        elements.push(<div key={i} className="h-1" />);
      } else {
        elements.push(
          <p key={i} className="text-sm text-foreground/90 leading-relaxed">
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
        <h2 className="text-base font-bold">🤖 AI 작품 분석</h2>
        {!analysis && !loading && (
          <button
            onClick={handleAnalyze}
            className="px-4 py-1.5 text-sm font-medium rounded-full text-white transition-opacity hover:opacity-90 cursor-pointer"
            style={{ backgroundColor: platformColor }}
          >
            분석 시작
          </button>
        )}
      </div>

      {!analysis && !loading && !error && (
        <p className="text-sm text-muted-foreground text-center py-6">
          수집된 랭킹, 리뷰, 독자층 데이터를 AI가 종합 분석합니다.
        </p>
      )}

      {loading && (
        <div className="text-center py-8">
          <div
            className="inline-block w-6 h-6 border-2 border-t-transparent rounded-full animate-spin mb-2"
            style={{ borderColor: platformColor, borderTopColor: "transparent" }}
          />
          <p className="text-sm text-muted-foreground">AI가 데이터를 분석하고 있습니다...</p>
        </div>
      )}

      {error && (
        <div className="text-center py-6">
          <p className="text-sm text-red-500 mb-2">{error}</p>
          <button
            onClick={handleAnalyze}
            className="text-xs text-blue-500 hover:underline cursor-pointer"
          >
            다시 시도
          </button>
        </div>
      )}

      {analysis && (
        <div className="space-y-0.5">
          {renderAnalysis(analysis)}
          <div className="mt-4 pt-3 border-t text-xs text-muted-foreground flex items-center justify-between">
            <span>Claude Haiku · 수집 데이터 기반 분석</span>
            <button
              onClick={handleAnalyze}
              className="text-blue-500 hover:underline cursor-pointer"
            >
              재분석
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
