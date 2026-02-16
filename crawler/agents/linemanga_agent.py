"""
라인망가 (LINE マンガ) 크롤러 에이전트

특징:
- SSR+CSR 하이브리드 (domcontentloaded로 충분)
- 일본 IP 필수
- 90개 작품이 한 페이지에 로드됨 (스크롤 불필요)
- 셀렉터: .MdCMN05List ol > li (2026년 현재 구조)
"""

from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class LinemangaAgent(CrawlerAgent):
    """라인망가 웹 종합 랭킹 크롤러 에이전트"""

    def __init__(self):
        super().__init__(
            platform_id='linemanga',
            platform_name='라인망가 (웹 종합)',
            url='https://manga.line.me/periodic/gender_ranking?gender=0'
        )

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """
        라인망가 웹 종합 랭킹 50위 크롤링

        DOM 구조:
        <div class="MdCMN05List">
          <ol>
            <li>
              <a href="/product/periodic?id=..." title="제목">
                <span class="MdCMN14Num">1</span>
                <div class="MdCMN06Img"><img alt="제목" src="..."></div>
                <span class="mdCMN05Ttl">제목</span>
                <ul class="mdCMN05InfoList">
                  <li>ファンタジー・SF</li>
                  <li>毎週金曜更新</li>
                </ul>
              </a>
            </li>
          </ol>
        </div>
        """
        page = await browser.new_page()
        rankings = []

        try:
            self.logger.info(f"📱 {self.platform_name} 크롤링 중...")
            self.logger.info(f"   URL: {self.url}")

            await page.goto(self.url, wait_until='domcontentloaded', timeout=30000)

            # 랭킹 리스트가 나타날 때까지 대기
            try:
                await page.wait_for_selector('.MdCMN05List ol > li', timeout=15000)
            except Exception:
                # 실제 IP 차단 확인
                content = await page.content()
                if '日本国内' in content or len(content) < 1000:
                    self.logger.error("❌ 일본 IP가 필요합니다.")
                    raise Exception("IP 제한: 일본 IP 필요")
                raise

            # 추가 렌더링 대기
            await page.wait_for_timeout(2000)

            # 랭킹 아이템 추출
            items = await page.query_selector_all('.MdCMN05List ol > li')
            self.logger.info(f"   작품 요소 {len(items)}개 발견")

            for item in items[:50]:  # 상위 50개만
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

        # 링크 요소
        link = await item.query_selector('a[href*="/product/"]')
        if not link:
            return None

        # 1. 순위: <span class="MdCMN14Num">N</span>
        rank_el = await item.query_selector('.MdCMN14Num')
        if not rank_el:
            return None
        rank_text = (await rank_el.inner_text()).strip()
        try:
            rank = int(rank_text)
        except ValueError:
            return None

        # 2. 제목: title 속성 또는 <span class="mdCMN05Ttl">
        title = await link.get_attribute('title')
        if not title:
            title_el = await item.query_selector('.mdCMN05Ttl')
            if title_el:
                title = (await title_el.inner_text()).strip()
        if not title:
            return None

        # 3. URL
        href = await link.get_attribute('href') or ''
        url = f"https://manga.line.me{href}" if href and not href.startswith('http') else href

        # 4. 장르: <ul class="mdCMN05InfoList"><li>장르</li>...</ul>
        genre = ''
        genre_el = await item.query_selector('.mdCMN05InfoList li:first-child')
        if genre_el:
            genre = (await genre_el.inner_text()).strip()

        # 5. 썸네일: .MdCMN06Img img src
        thumbnail_url = ''
        thumb_img = await item.query_selector('.MdCMN06Img img')
        if thumb_img:
            thumbnail_url = await thumb_img.get_attribute('src') or ''

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
        print("라인망가 에이전트 테스트")
        print("=" * 60)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            try:
                agent = LinemangaAgent()
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
