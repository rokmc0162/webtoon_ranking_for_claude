"""
메챠코믹 (めちゃコミック) 크롤러 에이전트

특징:
- CSR 방식 (Playwright 필수)
- Tailwind CSS 기반 UI (2026년 리뉴얼 버전 대응)
- 단일 페이지에 전체 랭킹 표시 (ul.grid > li 구조)
- IP 제한 없음 (한국에서도 접근 가능)
- 카테고리별 랭킹: ?category= 파라미터로 구분
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class MechacomicAgent(CrawlerAgent):
    """메챠코믹 판매 랭킹 + 카테고리별 크롤러 에이전트"""

    # 카테고리별 랭킹 매핑 (URL: ?genre=N)
    # 성인 장르(TL/BL/オトナ/レディコミ)는 /r/ 접두사 경로 + 연령확인 필요
    GENRE_RANKINGS = {
        '': {'name': '종합', 'genre_id': ''},
        '少女': {'name': '소녀', 'genre_id': '2'},
        '女性': {'name': '여성', 'genre_id': '4'},
        '少年': {'name': '소년', 'genre_id': '1'},
        '青年': {'name': '청년', 'genre_id': '3'},
        'ハーレクイン': {'name': '할리퀸', 'genre_id': '40'},
        'TL': {'name': 'TL', 'genre_id': '6', 'adult': True},
        'BL': {'name': 'BL', 'genre_id': '24', 'adult': True},
        'オトナ': {'name': '오토나(어덜트)', 'genre_id': '5', 'adult': True},
    }

    def __init__(self):
        super().__init__(
            platform_id='mechacomic',
            platform_name='메챠코믹 (판매)',
            url='https://mechacomic.jp/sales_rankings/current'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """
        메챠코믹 종합 + 카테고리별 판매 랭킹 크롤링

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
        # 연령확인 쿠키 설정: 이 쿠키가 없으면 독占先行 작품이 랭킹에서 제외됨
        context = await browser.new_context()
        await context.add_cookies([{
            'name': '_confirmed_adult',
            'value': '1',
            'domain': 'mechacomic.jp',
            'path': '/',
        }])
        page = await context.new_page()
        all_rankings = []

        try:
            for genre_key, genre_info in self.GENRE_RANKINGS.items():
                label = genre_info['name']
                genre_id = genre_info['genre_id']
                self.logger.info(f"📱 메챠코믹 [{label}] 크롤링 중...")

                try:
                    rankings = await self._crawl_category(page, genre_id, genre_key)
                    self.genre_results[genre_key] = rankings
                    self.logger.info(f"   ✅ [{label}]: {len(rankings)}개 작품")
                except Exception as e:
                    self.logger.warning(f"   ⚠️ [{label}] 크롤링 실패: {e}")
                    self.genre_results[genre_key] = []
                    continue

                # 종합 랭킹은 반환값으로 사용
                if genre_key == '':
                    all_rankings = rankings

            return all_rankings

        finally:
            await page.close()
            await context.close()

    async def _crawl_category(self, page, genre_id: str, genre_key: str) -> List[Dict[str, Any]]:
        """특정 카테고리의 랭킹 크롤링 (5페이지, 상위 100개)"""
        rankings = []
        is_adult = self.GENRE_RANKINGS.get(genre_key, {}).get('adult', False)

        for page_num in range(1, 6):
            # URL 구성: genre + page 파라미터
            # 성인 장르는 /r/ 접두사 경로 사용
            base_url = self.url
            if is_adult:
                base_url = base_url.replace('mechacomic.jp/', 'mechacomic.jp/r/')

            params = []
            if genre_id:
                params.append(f'genre={genre_id}')
            if page_num > 1:
                params.append(f'page={page_num}')
            url = f'{base_url}?{"&".join(params)}' if params else base_url

            self.logger.info(f"   📄 페이지 {page_num}: {url}")
            await page.goto('about:blank')
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)

            # 성인 장르: 연령확인 다이얼로그 자동 처리 ("はい" 클릭)
            # 매 페이지마다 확인 (세션이 끊길 수 있음)
            if is_adult:
                try:
                    yes_btn = await page.wait_for_selector('button:has-text("はい")', timeout=5000)
                    if yes_btn:
                        await yes_btn.click()
                        self.logger.info(f"   🔞 연령확인 다이얼로그 승인")
                        await page.wait_for_timeout(3000)
                except Exception:
                    pass  # 다이얼로그가 없으면 무시

            # 랭킹 리스트 로드 대기 (성인 장르는 더 긴 타임아웃)
            wait_timeout = 20000 if is_adult else 15000
            try:
                await page.wait_for_selector('ul.grid li', timeout=wait_timeout)
            except Exception:
                # 셀렉터 대기 실패 시 추가 대기 후 재시도
                self.logger.warning(f"   ⚠️ 페이지 {page_num} ul.grid li 대기 실패, 재시도...")
                await page.wait_for_timeout(3000)
                # li가 하나도 없으면 이 페이지 스킵
                check = await page.query_selector_all('ul.grid.grid-cols-1 > li')
                if not check:
                    self.logger.warning(f"   ⚠️ 페이지 {page_num} 랭킹 아이템 없음, 스킵")
                    break
            await page.wait_for_timeout(2000)

            items = await page.query_selector_all('ul.grid.grid-cols-1 > li')

            for item in items:
                try:
                    entry = await self._parse_item(item)
                    if entry:
                        if genre_key and not entry['genre']:
                            entry['genre'] = genre_key
                        rankings.append(entry)
                except Exception as e:
                    self.logger.debug(f"개별 작품 파싱 실패: {e}")
                    continue

        rankings.sort(key=lambda x: x['rank'])
        return rankings[:100]

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

    async def save(self, date: str, data: List[Dict[str, Any]]):
        """종합 + 카테고리별 랭킹 모두 저장"""
        from crawler.db import save_rankings, backup_to_json, save_works_metadata

        # 종합 랭킹 저장
        save_rankings(date, self.platform_id, data, sub_category='')
        works_meta = [
            {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
             'url': item.get('url', ''), 'genre': item.get('genre', ''), 'rank': item.get('rank')}
            for item in data if item.get('thumbnail_url')
        ]
        if works_meta:
            save_works_metadata(self.platform_id, works_meta, date=date, sub_category='')
        backup_to_json(date, self.platform_id, data)

        # 카테고리별 랭킹 저장
        for genre_key, rankings in self.genre_results.items():
            if genre_key == '':
                continue
            genre_name = self.GENRE_RANKINGS[genre_key]['name']
            save_rankings(date, self.platform_id, rankings, sub_category=genre_key)
            genre_meta = [
                {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
                 'url': item.get('url', ''), 'genre': item.get('genre', ''), 'rank': item.get('rank')}
                for item in rankings if item.get('thumbnail_url')
            ]
            if genre_meta:
                save_works_metadata(self.platform_id, genre_meta, date=date, sub_category=genre_key)
            self.logger.info(f"   💾 [{genre_name}]: {len(rankings)}개 저장")


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

                    # 카테고리별 결과 요약
                    print(f"\n카테고리별 결과:")
                    for gkey, rankings in agent.genre_results.items():
                        label = agent.GENRE_RANKINGS[gkey]['name']
                        print(f"  [{label}]: {len(rankings)}개")
                else:
                    print(f"\n❌ Error: {result.error}")

            finally:
                await browser.close()

        print("\n" + "=" * 60)

    asyncio.run(test())
