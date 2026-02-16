"""
픽코마 (ピッコマ) 크롤러 에이전트

특징:
- SSR 방식 (HTML에 모든 데이터 포함, 가장 쉬움)
- SMARTOON 종합 랭킹 크롤링
- 일본 IP 필수
"""

from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent
from crawler.utils import get_korean_title, is_riverse_title, translate_genre


class PiccomaAgent(CrawlerAgent):
    """픽코마 SMARTOON 종합 랭킹 크롤러 에이전트"""

    def __init__(self):
        super().__init__(
            platform_id='piccoma',
            platform_name='픽코마 (SMARTOON)',
            url='https://piccoma.com/web/ranking/S/P/0'
        )

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """
        픽코마 SMARTOON 종합 랭킹 50위 크롤링

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

            # SSR 방식이므로 domcontentloaded면 충분
            await page.goto(self.url, wait_until='domcontentloaded', timeout=30000)

            # SSR이므로 즉시 데이터 있음, 하지만 안전하게 대기
            await page.wait_for_selector(
                '.PCM-productList_item, .ranking-item, article',
                timeout=10000
            )

            # 작품 요소 추출
            items = await page.query_selector_all(
                '.PCM-productList_item, .ranking-item, article, li'
            )

            self.logger.info(f"   작품 요소 {len(items)}개 발견")

            for i, item in enumerate(items[:50], 1):  # 상위 50개만
                try:
                    # 순위 추출
                    rank = await self._extract_rank(item, i)

                    # 제목 추출
                    title = await self._extract_title(item)

                    if not title:
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

    async def _extract_rank(self, item, fallback: int) -> int:
        """순위 추출 (selector 우선, fallback은 순서)"""
        rank_elem = await item.query_selector('.rank, .ranking-number, .number')

        if rank_elem:
            rank_text = await rank_elem.inner_text()
            try:
                return int(rank_text.strip().replace('位', '').replace('#', ''))
            except ValueError:
                pass

        return fallback

    async def _extract_title(self, item) -> str:
        """제목 추출 (여러 방법 시도)"""
        # Method 1: title class
        title_elem = await item.query_selector('.PCM-product-title, .title, h3, h2')
        if title_elem:
            title = await title_elem.inner_text()
            if title:
                return title.strip()

        # Method 2: link attributes
        link_elem = await item.query_selector('a')
        if link_elem:
            title = await link_elem.get_attribute('aria-label')
            if title:
                return title.strip()

            title = await link_elem.get_attribute('title')
            if title:
                return title.strip()

        # Method 3: 전체 텍스트 파싱
        text = await item.inner_text()
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        for line in lines:
            if len(line) > 3 and '位' not in line and '#' not in line:
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
            return f"https://piccoma.com{url_path}"

    async def _extract_genre(self, item) -> str:
        """장르 추출"""
        # Method 1: selector
        genre_elem = await item.query_selector('.genre, .category, .tag')
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
        print("픽코마 에이전트 테스트")
        print("=" * 60)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)

            try:
                agent = PiccomaAgent()
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
