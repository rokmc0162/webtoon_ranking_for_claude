"use client";

import { type ReactElement, useState, useEffect } from "react";

interface AiAnalysisProps {
  platform: string;
  title: string;
  platformColor: string;
}

export function AiAnalysis({ platform, title, platformColor }: AiAnalysisProps) {
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState("");

  const apiBase = `/api/title-analysis?platform=${encodeURIComponent(platform)}&title=${encodeURIComponent(title)}`;

  // 마운트 시 캐시된 분석 자동 로드
  useEffect(() => {
    fetch(apiBase)
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
  }, [apiBase]);

  const handleAnalyze = (refresh: boolean) => {
    setLoading(true);
    setError("");

    const url = refresh ? `${apiBase}&refresh=true` : apiBase;

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
    const cleaned = text
      .replace(/#{1,4}\s*/g, "")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/\*([^*]+)\*/g, "$1")
      .replace(/^[-•]\s+/gm, "")
      .replace(/\(웹\)/g, "")
      .replace(/\(DB\)/g, "")
      .replace(/\(웹 검색 기반\)/g, "");

    const lines = cleaned.split("\n");
    const elements: ReactElement[] = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      if (/^\d+\.\s+.+/.test(line) && line.length < 30) {
        elements.push(
          <h3
            key={i}
            className="text-sm font-bold mt-6 mb-2 tracking-tight"
            style={{ color: platformColor }}
          >
            {line}
          </h3>
        );
      } else if (line === "") {
        elements.push(<div key={i} className="h-1.5" />);
      } else {
        elements.push(
          <p key={i} className="text-sm text-foreground/90 leading-[1.85]">
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
        {!analysis && !loading && !initialLoading && (
          <button
            onClick={() => handleAnalyze(false)}
            className="px-4 py-1.5 text-sm font-medium rounded-full text-white transition-opacity hover:opacity-90 cursor-pointer"
            style={{ backgroundColor: platformColor }}
          >
            분석 시작
          </button>
        )}
      </div>

      {initialLoading && (
        <div className="text-center py-6">
          <div
            className="inline-block w-5 h-5 border-2 border-t-transparent rounded-full animate-spin"
            style={{ borderColor: platformColor, borderTopColor: "transparent" }}
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
            style={{ borderColor: platformColor, borderTopColor: "transparent" }}
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
            style={{ color: platformColor }}
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
              style={{ color: platformColor }}
            >
              재분석
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
