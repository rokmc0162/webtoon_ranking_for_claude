import { SearchClient } from "@/components/search-client";

// 정적 페이지 — DB 조회 불필요 (검색은 클라이언트에서 API 호출)
export default function SearchPage() {
  return <SearchClient />;
}
