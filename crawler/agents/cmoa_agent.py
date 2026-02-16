"""
코믹시모아 (コミックシーモア) 크롤러 에이전트

특징:
- CSR + TLS 이슈 (Playwright 필수, ignore_https_errors)
- 단일 페이지에 200개 표시, 상위 50개 사용
- IP 제한 없음
- 셀렉터: li.search_result_box (2026년 현재 구조)
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


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

        DOM 구조:
        <li class="search_result_box">
          <div class="search_result_box_left">
            <a href="/title/{id}/" class="title">
              <img class="volume_img" alt="제목" src="...">
            </a>
          </div>
          <div class="search_result_box_right">
            <div class="rank_area">
              <p class="title_rank r1">1位</p>
            </div>
            <div class="search_result_box_right_sec1">
              <a href="/title/{id}/" class="title">제목</a>
            </div>
            <div class="search_result_box_right_sec2">
              <p>ジャンル：<a href="/search/genre/2/">女性マンガ</a></p>
            </div>
          </div>
        </li>
        """
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()
        rankings = []

        try:
            self.logger.info(f"📱 {self.platform_name} 크롤링 중...")
            self.logger.info(f"   URL: {self.url}")

            await page.goto(self.url, wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_selector('li.search_result_box', timeout=10000)
            await page.wait_for_timeout(1000)

            items = await page.query_selector_all('li.search_result_box')
            self.logger.info(f"   작품 요소 {len(items)}개 발견")

            for item in items[:50]:
                try:
                    entry = await self._parse_item(item)
                    if entry:
                        rankings.append(entry)
                except Exception as e:
                    self.logger.debug(f"작품 파싱 실패: {e}")
                    continue

            # 순위 정렬
            rankings.sort(key=lambda x: x['rank'])

            self.logger.info(f"   ✅ {self.platform_name}: {len(rankings)}개 작품 수집 완료")
            return rankings

        finally:
            await page.close()
            await context.close()

    async def _parse_item(self, item) -> Dict[str, Any]:
        """개별 랭킹 아이템 파싱"""

        # 1. 순위: .title_rank 텍스트에서 숫자 추출
        rank_el = await item.query_selector('.title_rank')
        if not rank_el:
            return None
        rank_text = (await rank_el.inner_text()).strip()
        match = re.search(r'(\d+)位', rank_text)
        if not match:
            return None
        rank = int(match.group(1))

        # 2. 제목: .search_result_box_right_sec1 a.title
        title = None
        title_el = await item.query_selector('.search_result_box_right_sec1 a.title')
        if title_el:
            title = (await title_el.inner_text()).strip()

        # fallback: img alt
        if not title:
            img_el = await item.query_selector('img.volume_img')
            if img_el:
                title = await img_el.get_attribute('alt')

        if not title:
            return None

        # 3. URL: a.title href
        url = ''
        if title_el:
            href = await title_el.get_attribute('href')
            if href:
                url = f"https://www.cmoa.jp{href}" if not href.startswith('http') else href

        # 4. 장르: "ジャンル：" 다음의 <a> 태그
        genre = ''
        sec2 = await item.query_selector('.search_result_box_right_sec2')
        if sec2:
            sec2_html = await sec2.inner_html()
            genre_match = re.search(r'ジャンル：\s*<a[^>]*>([^<]+)</a>', sec2_html)
            if genre_match:
                genre = genre_match.group(1).strip()

        # 5. 썸네일: data-src (lazy loading) → src fallback
        thumbnail_url = ''
        thumb_el = await item.query_selector('img.volume_img')
        if thumb_el:
            # data-src에 실제 URL이 있음 (lazy loading)
            thumb_src = await thumb_el.get_attribute('data-src') or ''
            if not thumb_src:
                thumb_src = await thumb_el.get_attribute('src') or ''
            if thumb_src and 'loader.png' not in thumb_src:
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
        print("코믹시모아 에이전트 테스트")
        print("=" * 60)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            try:
                agent = CmoaAgent()
                result = await agent.execute(browser)

                print(f"\n✅ Success: {result.success}")
                print(f"✅ Count: {result.count}")

                if result.success and result.data:
                    print(f"\n샘플 (1~5위):")
                    for item in result.data[:5]:
                        print(f"  {item['rank']}위: {item['title'][:40]}")
                        print(f"    장르: {item['genre']}")
                        print(f"    URL: {item['url']}")
                else:
                    print(f"\n❌ Error: {result.error}")

            finally:
                await browser.close()

        print("\n" + "=" * 60)

    asyncio.run(test())
