"""
메챠코믹 (め

ちゃコミック) 크롤러 에이전트

특징:
- CSR 방식 (Playwright 필수)
- 페이지네이션 3페이지 (약 50개 작품)
- IP 제한 없음 (한국에서도 테스트 가능)

개선사항:
- wait_until='networkidle' → 'domcontentloaded' (timeout 문제 해결)
- 재시도 로직 추가
- 에이전트 기반 아키텍처
"""

from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent
from crawler.utils import get_korean_title, is_riverse_title, translate_genre


class MechacomicAgent(CrawlerAgent):
    """메챠코믹 판매 랭킹 크롤러 에이전트"""

    def __init__(self):
        super().__init__(
            platform_id='mechacomic',
            platform_name='메챠코믹 (판매)',
            url='https://mechacomic.jp/sales_rankings/current'
        )

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """
        메챠코믹 판매 랭킹 50위 크롤링

        Args:
            browser: Playwright 브라우저 인스턴스

        Returns:
            [{'rank': 1, 'title': '제목', 'genre': '장르', 'url': 'http://...'}, ...]
        """
        page = await browser.new_page()
        rankings = []

        try:
            self.logger.info(f"📱 {self.platform_name} 크롤링 중...")
            self.logger.info(f"   URL: {self.url}")

            # 3페이지 순회 (각 페이지 약 17개 작품)
            for page_num in range(1, 4):
                url = f'{self.url}?page={page_num}'
                self.logger.debug(f"페이지 {page_num} 접속 중...")

                # 수정: wait_until='domcontentloaded' (networkidle 대신)
                # 이유: networkidle은 모든 네트워크 활동이 멈출 때까지 대기하여 timeout 발생
                await page.goto(url, wait_until='domcontentloaded', timeout=20000)

                # JavaScript 렌더링 대기
                # 수정: 더 구체적인 selector로 변경 (실제 DOM 구조에 맞게)
                # 기존: '.ranking-item, .rank-item, article' (너무 범용적)
                # 개선: 실제 셀렉터 확인 후 사용
                try:
                    await page.wait_for_selector(
                        '.c-card, .ranking__item, .rank-item, article',
                        timeout=10000
                    )
                except Exception:
                    # Selector 대기 실패 시 추가 대기
                    await page.wait_for_timeout(2000)

                # 작품 요소 추출
                items = await page.query_selector_all(
                    '.c-card, .ranking__item, .rank-item, article'
                )

                self.logger.debug(f"페이지 {page_num}: {len(items)}개 요소 발견")

                for item in items:
                    try:
                        # 순위 추출 ("N位" 텍스트 찾기)
                        rank_text = await item.inner_text()
                        rank = self._extract_rank(rank_text)

                        if not rank:
                            continue  # 순위 없으면 스킵

                        # 제목 추출
                        title = await self._extract_title(item, rank_text)

                        if not title:
                            continue

                        # URL 추출
                        url_full = await self._extract_url(item)

                        # 장르 추출 (텍스트에서 키워드 매칭)
                        genre = self._extract_genre(rank_text)

                        # 한국어 제목 및 리버스 여부 확인
                        title_kr = get_korean_title(title)
                        is_riverse = is_riverse_title(title)
                        genre_kr = translate_genre(genre)

                        rankings.append({
                            'rank': rank,
                            'title': title.strip(),
                            'title_kr': title_kr,
                            'genre': genre,
                            'genre_kr': genre_kr,
                            'url': url_full,
                            'is_riverse': is_riverse
                        })

                    except Exception as e:
                        self.logger.debug(f"개별 작품 파싱 실패: {e}")
                        continue

            # 중복 제거 및 순위 정렬
            unique_rankings = self._deduplicate(rankings)

            # 상위 50개만
            result = unique_rankings[:50]

            self.logger.info(f"   ✅ {self.platform_name}: {len(result)}개 작품 수집 완료")
            return result

        finally:
            await page.close()

    def _extract_rank(self, text: str) -> int:
        """순위 추출 ("N位" 패턴 찾기)"""
        if '位' not in text:
            return None

        for line in text.split('\n'):
            if '位' in line:
                try:
                    return int(line.replace('位', '').strip())
                except ValueError:
                    continue

        return None

    async def _extract_title(self, item, fallback_text: str) -> str:
        """제목 추출 (selector 우선, fallback으로 텍스트 파싱)"""
        # Method 1: selector로 찾기
        title_elem = await item.query_selector('.title, .work-title, h3, h2')
        if title_elem:
            title = await title_elem.inner_text()
            if title:
                return title.strip()

        # Method 2: 텍스트에서 제목 추출 (첫 번째 긴 줄)
        lines = fallback_text.split('\n')
        for line in lines:
            line = line.strip()
            if len(line) > 3 and '位' not in line:
                return line

        return ""

    async def _extract_url(self, item) -> str:
        """URL 추출"""
        link_elem = await item.query_selector('a')
        if not link_elem:
            return ""

        url_path = await link_elem.get_attribute('href')
        if not url_path:
            return ""

        if url_path.startswith('http'):
            return url_path
        else:
            return f"https://mechacomic.jp{url_path}"

    def _extract_genre(self, text: str) -> str:
        """텍스트에서 장르 키워드 추출"""
        genres = [
            'ファンタジー', '恋愛', 'アクション', 'ドラマ', 'ホラー', 'ミステリー',
            'コメディ', 'サスペンス', 'SF', '学園', 'スポーツ', 'グルメ',
            '日常', 'BL', 'TL', '異世界', '転生', '復讐', 'バトル'
        ]

        for genre in genres:
            if genre in text:
                return genre

        return ""

    def _deduplicate(self, rankings: List[Dict]) -> List[Dict]:
        """중복 제거 및 순위 정렬"""
        seen = set()
        unique = []

        for item in rankings:
            if item['rank'] not in seen:
                seen.add(item['rank'])
                unique.append(item)

        unique.sort(key=lambda x: x['rank'])
        return unique


if __name__ == "__main__":
    # 테스트 코드
    import asyncio
    from playwright.async_api import async_playwright

    async def test():
        print("=" * 60)
        print("메챠코믹 에이전트 테스트")
        print("=" * 60)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)  # 디버깅용

            try:
                agent = MechacomicAgent()
                result = await agent.execute(browser)

                print(f"\n✅ Success: {result.success}")
                print(f"✅ Count: {result.count}")

                if result.success and result.data:
                    print(f"\n샘플 (1~3위):")
                    for item in result.data[:3]:
                        print(f"  {item['rank']}위: {item['title']}")
                        if item['title_kr']:
                            print(f"    한국어: {item['title_kr']}")
                        print(f"    장르: {item['genre']} ({item['genre_kr']})")
                        print(f"    리버스: {item['is_riverse']}")
                else:
                    print(f"\n❌ Error: {result.error}")

            finally:
                await browser.close()

        print("\n" + "=" * 60)

    asyncio.run(test())
