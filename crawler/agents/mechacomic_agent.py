"""
메챠코믹 (めちゃコミック) 크롤러 에이전트

특징:
- CSR 방식 (Playwright 필수)
- Tailwind CSS 기반 UI (2026년 리뉴얼 버전 대응)
- 단일 페이지에 전체 랭킹 표시 (ul.grid > li 구조)
- IP 제한 없음 (한국에서도 접근 가능)
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


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
        메챠코믹 데일리 판매 랭킹 크롤링

        DOM 구조 (2026년 Tailwind CSS 리뉴얼 버전):
        <ul class="grid grid-cols-1 lg:grid-cols-2">
          <li>
            <div class="flex gap-2.5 ...">
              <div>  <!-- 이미지 영역 -->
                <a href="/books/{id}"><img alt="제목" ...></a>
              </div>
              <div>  <!-- 정보 영역 -->
                <span class="... font-bold">1位</span>
                <a href="/books/{id}" class="font-bold text-link">제목</a>
                <div class="text-[12px]">작가명</div>
                <span class="inline-flex ...">장르태그</span>
              </div>
            </div>
          </li>
        </ul>
        """
        page = await browser.new_page()
        rankings = []

        try:
            self.logger.info(f"📱 {self.platform_name} 크롤링 중...")
            self.logger.info(f"   URL: {self.url}")

            # 3페이지 순회 (각 20개씩, 총 60개 중 상위 50개 사용)
            for page_num in range(1, 4):
                url = f'{self.url}?page={page_num}' if page_num > 1 else self.url
                self.logger.debug(f"   페이지 {page_num} 접속 중...")

                await page.goto(url, wait_until='domcontentloaded', timeout=30000)

                # JS 렌더링 대기 - 랭킹 그리드가 나타날 때까지
                await page.wait_for_selector(
                    'ul.grid li',
                    timeout=15000
                )
                await page.wait_for_timeout(1500)

                # 랭킹 리스트 아이템 추출
                items = await page.query_selector_all('ul.grid.grid-cols-1 > li')
                self.logger.debug(f"   페이지 {page_num}: {len(items)}개 요소 발견")

                for item in items:
                    try:
                        ranking_entry = await self._parse_item(item)
                        if ranking_entry:
                            rankings.append(ranking_entry)
                    except Exception as e:
                        self.logger.debug(f"개별 작품 파싱 실패: {e}")
                        continue

            # 순위 정렬 및 상위 50개
            rankings.sort(key=lambda x: x['rank'])
            result = rankings[:50]

            self.logger.info(f"   ✅ {self.platform_name}: {len(result)}개 작품 수집 완료")
            return result

        finally:
            await page.close()

    async def _parse_item(self, item) -> Dict[str, Any]:
        """개별 랭킹 아이템 파싱"""

        # 1. 순위 추출: <span class="... font-bold">N位</span>
        rank_spans = await item.query_selector_all('span')
        rank = None
        for span in rank_spans:
            text = await span.inner_text()
            text = text.strip()
            match = re.match(r'^(\d+)位$', text)
            if match:
                rank = int(match.group(1))
                break

        if rank is None:
            return None

        # 2. 제목 추출: <a class="font-bold text-link ...">제목</a>
        title = None
        title_links = await item.query_selector_all('a.font-bold')
        for link in title_links:
            cls = await link.get_attribute('class') or ''
            if 'text-link' in cls:
                title = (await link.inner_text()).strip()
                break

        if not title:
            # fallback: 이미지 alt 속성에서 제목 추출
            img = await item.query_selector('img[alt]:not([alt=""])')
            if img:
                alt = await img.get_attribute('alt')
                # 아이콘 이미지 제외 (オリジナル, 独占先行, 続話 등)
                if alt and len(alt) > 3 and alt not in [
                    'オリジナル', '独占先行', '続話', '毎日無料プラス'
                ]:
                    title = alt.strip()

        if not title:
            return None

        # 3. URL 추출: /books/{id}
        url = ''
        book_link = await item.query_selector('a[href*="/books/"]')
        if book_link:
            href = await book_link.get_attribute('href')
            if href:
                url = f"https://mechacomic.jp{href}" if not href.startswith('http') else href

        # 4. 장르 태그 추출: <span class="inline-flex items-center ...">장르</span>
        genres = []
        genre_spans = await item.query_selector_all('span.inline-flex')
        for gs in genre_spans:
            genre_text = (await gs.inner_text()).strip()
            if genre_text:
                genres.append(genre_text)

        # 첫 번째 장르를 메인 장르로 사용
        genre = genres[0] if genres else ''

        # 5. 썸네일: /images/book/ 경로의 실제 표지 이미지 (아이콘 제외)
        thumbnail_url = ''
        all_imgs = await item.query_selector_all('img[alt]:not([alt=""])')
        for img in all_imgs:
            src = await img.get_attribute('src') or ''
            if '/images/book/' in src:
                thumbnail_url = src
                break

        return {
            'rank': rank,
            'title': title,
            'genre': genre,
            'url': url,
            'thumbnail_url': thumbnail_url,
        }


if __name__ == "__main__":
    import asyncio
    from playwright.async_api import async_playwright

    async def test():
        print("=" * 60)
        print("메챠코믹 에이전트 테스트")
        print("=" * 60)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            try:
                agent = MechacomicAgent()
                result = await agent.execute(browser)

                print(f"\n✅ Success: {result.success}")
                print(f"✅ Count: {result.count}")

                if result.success and result.data:
                    print(f"\n샘플 (1~5위):")
                    for item in result.data[:5]:
                        print(f"  {item['rank']}위: {item['title']}")
                        print(f"    장르: {item['genre']}")
                        print(f"    URL: {item['url']}")
                else:
                    print(f"\n❌ Error: {result.error}")

            finally:
                await browser.close()

        print("\n" + "=" * 60)

    asyncio.run(test())
