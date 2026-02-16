"""
픽코마 (ピッコマ) 크롤러 에이전트

특징:
- SSR 방식 (HTML에 모든 데이터 포함)
- SMARTOON 종합 랭킹 크롤링
- 일본 IP 필수
- 셀렉터: .PCM-productTile ul > li (2026년 현재 구조)
"""

from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


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

        DOM 구조:
        <div class="PCM-productTile PCOM-component">
          <ul>
            <li>
              <a href="/web/product/{id}">
                <img alt="제목" src="...">
                <div class="PCM-rankingProduct_rankNum">1</div>
                <div class="PCM-rankingProduct_rankChangeNum">11</div>
                <div class="PCM-l_rankingProduct_name">제목</div>
                <div class="PCM-l_rankingProduct_author">작가명</div>
              </a>
            </li>
          </ul>
        </div>
        """
        page = await browser.new_page()
        rankings = []

        try:
            self.logger.info(f"📱 {self.platform_name} 크롤링 중...")
            self.logger.info(f"   URL: {self.url}")

            await page.goto(self.url, wait_until='domcontentloaded', timeout=30000)

            # 랭킹 리스트 대기
            await page.wait_for_selector('.PCM-productTile ul > li', timeout=10000)
            await page.wait_for_timeout(1000)

            # 작품 아이템 추출 (정확히 50개)
            items = await page.query_selector_all('.PCM-productTile ul > li')
            self.logger.info(f"   작품 요소 {len(items)}개 발견")

            for item in items[:50]:
                try:
                    entry = await self._parse_item(item)
                    if entry:
                        rankings.append(entry)
                except Exception as e:
                    self.logger.debug(f"작품 파싱 실패: {e}")
                    continue

            self.logger.info(f"   ✅ {self.platform_name}: {len(rankings)}개 작품 수집 완료")
            return rankings

        finally:
            await page.close()

    async def _parse_item(self, item) -> Dict[str, Any]:
        """개별 랭킹 아이템 파싱"""

        # 1. 순위: .PCM-rankingProduct_rankNum
        rank_el = await item.query_selector('.PCM-rankingProduct_rankNum')
        if not rank_el:
            return None
        rank_text = (await rank_el.inner_text()).strip()
        try:
            rank = int(rank_text)
        except ValueError:
            return None

        # 2. 제목: img[alt] (가장 신뢰할 수 있는 소스)
        title = None
        img_el = await item.query_selector('img[alt]')
        if img_el:
            title = await img_el.get_attribute('alt')

        # fallback: .PCM-l_rankingProduct_name
        if not title:
            name_el = await item.query_selector('.PCM-l_rankingProduct_name')
            if name_el:
                title = (await name_el.inner_text()).strip()

        if not title:
            return None

        # 3. URL: a[href*="/web/product"]
        url = ''
        link_el = await item.query_selector('a[href*="/web/product"]')
        if link_el:
            href = await link_el.get_attribute('href')
            if href:
                url = f"https://piccoma.com{href}" if not href.startswith('http') else href

        # 4. 장르: 픽코마 랭킹 페이지에는 장르 정보가 없음 (빈 문자열)
        genre = ''

        # 5. 썸네일: data-original (lazy loading) → src fallback
        thumbnail_url = ''
        if img_el:
            # data-original에 실제 URL이 있음 (lazy loading)
            thumb_src = await img_el.get_attribute('data-original') or ''
            if not thumb_src:
                thumb_src = await img_el.get_attribute('src') or ''
            if thumb_src and 'ph_cover.png' not in thumb_src:
                thumbnail_url = f"https:{thumb_src}" if thumb_src.startswith('//') else thumb_src

        return {
            'rank': rank,
            'title': title.strip(),
            'genre': genre,
            'url': url,
            'thumbnail_url': thumbnail_url,
        }


if __name__ == "__main__":
    import asyncio
    from playwright.async_api import async_playwright

    async def test():
        print("=" * 60)
        print("픽코마 에이전트 테스트")
        print("=" * 60)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            try:
                agent = PiccomaAgent()
                result = await agent.execute(browser)

                print(f"\n✅ Success: {result.success}")
                print(f"✅ Count: {result.count}")

                if result.success and result.data:
                    print(f"\n샘플 (1~5위):")
                    for item in result.data[:5]:
                        print(f"  {item['rank']}위: {item['title']}")
                        print(f"    URL: {item['url']}")
                else:
                    print(f"\n❌ Error: {result.error}")

            finally:
                await browser.close()

        print("\n" + "=" * 60)

    asyncio.run(test())
