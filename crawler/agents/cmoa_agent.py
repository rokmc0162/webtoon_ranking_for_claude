"""
코믹시모아 (コミックシーモア) 크롤러 에이전트

특징:
- CSR + TLS 이슈 (fetch 시 에러, Playwright 필수)
- 단일 페이지 (50개 작품)
- IP 제한 없음

개선사항:
- selector 정확성 향상 (fallback selector 추가)
- wait_until='domcontentloaded' (timeout 문제 해결)
- 에이전트 기반 아키텍처
"""

from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent
from crawler.utils import get_korean_title, is_riverse_title, translate_genre


class CmoaAgent(CrawlerAgent):
    """코믹시모아 종합 랭킹 크롤러 에이전트"""

    def __init__(self):
        super().__init__(
            platform_id='cmoa',
            platform_name='코믹시모아 (종합)',
            url='https://www.cmoa.jp/search/purpose/ranking/all/'
        )

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """
        코믹시모아 종합 랭킹 50위 크롤링

        Args:
            browser: Playwright 브라우저 인스턴스

        Returns:
            [{'rank': 1, 'title': '제목', 'genre': '장르', 'url': 'http://...'}, ...]
        """
        # TLS 에러 우회를 위해 ignore_https_errors 설정
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()
        rankings = []

        try:
            self.logger.info(f"📱 {self.platform_name} 크롤링 중...")
            self.logger.info(f"   URL: {self.url}")

            # 수정: wait_until='domcontentloaded' (networkidle 대신)
            await page.goto(self.url, wait_until='domcontentloaded', timeout=20000)

            # JavaScript 렌더링 대기
            # 수정: 여러 selector 시도 (실제 DOM에 맞게)
            selectors_to_try = [
                'li.search_result_box',  # 가장 가능성 높음
                '.product-item',
                '.ranking-item',
                'div.item',
                '.work-item',
                'article'
            ]

            items = None
            matched_selector = None

            for selector in selectors_to_try:
                try:
                    await page.wait_for_selector(selector, timeout=8000)
                    test_items = await page.query_selector_all(selector)

                    if test_items and len(test_items) > 0:
                        items = test_items
                        matched_selector = selector
                        self.logger.debug(f"Selector '{selector}' 매칭: {len(items)}개 요소")
                        break
                except Exception:
                    continue

            if not items:
                # 최후의 수단: 모든 selector 결합
                combined_selector = ', '.join(selectors_to_try)
                items = await page.query_selector_all(combined_selector)
                matched_selector = "combined"

            self.logger.info(f"   작품 요소 {len(items)}개 발견 (selector: {matched_selector})")

            for i, item in enumerate(items[:50], 1):  # 상위 50개만
                try:
                    # 순위는 순서대로 나열됨
                    rank = i

                    # 제목 추출 (여러 방법 시도)
                    title = await self._extract_title(item)

                    if not title:
                        self.logger.debug(f"{i}번째 작품: 제목 추출 실패, 스킵")
                        continue

                    # URL 추출
                    url_full = await self._extract_url(item)

                    # 장르 추출
                    genre = await self._extract_genre(item)

                    # 한국어 제목 및 리버스 여부 확인
                    title_kr = get_korean_title(title)
                    is_riverse = is_riverse_title(title)
                    genre_kr = translate_genre(genre)

                    rankings.append({
                        'rank': rank,
                        'title': title.strip(),
                        'title_kr': title_kr,
                        'genre': genre.strip() if genre else "",
                        'genre_kr': genre_kr,
                        'url': url_full,
                        'is_riverse': is_riverse
                    })

                except Exception as e:
                    self.logger.debug(f"{i}번째 작품 파싱 실패: {e}")
                    continue

            self.logger.info(f"   ✅ {self.platform_name}: {len(rankings)}개 작품 수집 완료")
            return rankings

        finally:
            await page.close()
            await context.close()

    async def _extract_title(self, item) -> str:
        """
        제목 추출 (여러 방법 시도)

        우선순위:
        1. .title, .work-title selector
        2. h3, h2 태그
        3. 링크의 aria-label
        4. 링크 텍스트
        5. 전체 텍스트 파싱
        """
        # Method 1: title class
        for selector in ['.title', '.work-title', '.product-title']:
            title_elem = await item.query_selector(selector)
            if title_elem:
                title = await title_elem.inner_text()
                if title and len(title.strip()) > 0:
                    return title.strip()

        # Method 2: heading tags
        for selector in ['h3', 'h2', 'h4']:
            title_elem = await item.query_selector(selector)
            if title_elem:
                title = await title_elem.inner_text()
                if title and len(title.strip()) > 0:
                    return title.strip()

        # Method 3: link aria-label
        link_elem = await item.query_selector('a')
        if link_elem:
            aria_label = await link_elem.get_attribute('aria-label')
            if aria_label and len(aria_label.strip()) > 0:
                return aria_label.strip()

            # Method 4: link text
            link_text = await link_elem.inner_text()
            if link_text:
                # 첫 번째 줄을 제목으로 간주
                lines = link_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if len(line) > 2:
                        return line

        # Method 5: 전체 텍스트 파싱
        text = await item.inner_text()
        if text:
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if len(line) > 2:  # 최소 3글자 이상
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
            return f"https://www.cmoa.jp{url_path}"

    async def _extract_genre(self, item) -> str:
        """
        장르 추출

        우선순위:
        1. .genre, .category selector
        2. 텍스트에서 키워드 매칭
        """
        # Method 1: selector
        for selector in ['.genre', '.category', '.tag']:
            genre_elem = await item.query_selector(selector)
            if genre_elem:
                genre = await genre_elem.inner_text()
                if genre:
                    return genre.strip()

        # Method 2: 텍스트에서 키워드 매칭
        text = await item.inner_text()
        return self._extract_genre_from_text(text)

    def _extract_genre_from_text(self, text: str) -> str:
        """텍스트에서 장르 키워드 추출"""
        genres = [
            'ファンタジー', '恋愛', 'アクション', 'ドラマ', 'ホラー', 'ミステリー',
            'コメディ', 'サスペンス', 'SF', '学園', 'スポーツ', 'グルメ',
            '日常', 'BL', 'TL', '異世界', '転生', '復讐', 'バトル', '歴史'
        ]

        for genre in genres:
            if genre in text:
                return genre

        return ""


if __name__ == "__main__":
    # 테스트 코드
    import asyncio
    from playwright.async_api import async_playwright

    async def test():
        print("=" * 60)
        print("코믹시모아 에이전트 테스트")
        print("=" * 60)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)  # 디버깅용

            try:
                agent = CmoaAgent()
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
