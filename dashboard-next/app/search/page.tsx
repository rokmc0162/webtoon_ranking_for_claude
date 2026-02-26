import { Suspense } from "react";
import { SearchClient } from "@/components/search-client";

// 정적 페이지 — DB 조회 불필요 (검색은 클라이언트에서 API 호출)
// Suspense 필요: SearchClient가 useSearchParams() 사용
export default function SearchPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <SearchClient />
    </Suspense>
  );
}
