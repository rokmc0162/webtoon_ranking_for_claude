"""
픽코마 (ピッコマ) 크롤러 에이전트

특징:
- SSR 방식 (HTML에 모든 데이터 포함)
- SMARTOON 종합 랭킹 크롤링
- 일본 IP 필수
- 셀렉터: .PCM-productTile ul > li (2026년 현재 구조)
- 장르: 랭킹 페이지에 없음 → 개별 작품 페이지 JSON-LD에서 수집 후 캐시
"""

from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent
from crawler.db import get_works_genres, save_work_genre, update_rankings_genre
from crawler.utils import translate_genre


class PiccomaAgent(CrawlerAgent):
    """픽코마 SMARTOON 종합 + 장르별 랭킹 크롤러 에이전트"""

    # 장르별 랭킹 URL 매핑
    GENRE_RANKINGS = {
        '': {'name': '총합', 'path': '/web/ranking/S/P/0'},
        'ファンタジー': {'name': '판타지', 'path': '/web/ranking/S/P/2'},
        '恋愛': {'name': '연애', 'path': '/web/ranking/S/P/1'},
        'アクション': {'name': '액션', 'path': '/web/ranking/S/P/5'},
        'ドラマ': {'name': '드라마', 'path': '/web/ranking/S/P/3'},
        'ホラー・ミステリー': {'name': '호러/미스터리', 'path': '/web/ranking/S/P/7'},
        '裏社会・アングラ': {'name': '뒷세계/언더그라운드', 'path': '/web/ranking/S/P/9'},
        'スポーツ': {'name': '스포츠', 'path': '/web/ranking/S/P/6'},
        'グルメ': {'name': '요리', 'path': '/web/ranking/S/P/10'},
        '日常': {'name': '일상', 'path': '/web/ranking/S/P/4'},
        'TL': {'name': 'TL', 'path': '/web/ranking/S/P/13'},
        'BL': {'name': 'BL', 'path': '/web/ranking/S/P/14'},
    }

    def __init__(self):
        super().__init__(
            platform_id='piccoma',
            platform_name='픽코마 (SMARTOON)',
            url='https://piccoma.com/web/ranking/S/P/0'
        )
        # 장르별 크롤링 결과 저장 (orchestrator에서 참조)
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """픽코마 SMARTOON 종합 + 장르별 랭킹 크롤링"""
        page = await browser.new_page()
        all_rankings = []

        try:
            for genre_key, genre_info in PiccomaAgent.GENRE_RANKINGS.items():
                url = f"https://piccoma.com{genre_info['path']}"
                label = genre_info['name']

                self.logger.info(f"📱 픽코마 [{label}] 크롤링 중... → {url}")

                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_selector('.PCM-productTile ul > li', timeout=10000)
                await page.wait_for_timeout(500)

                items = await page.query_selector_all('.PCM-productTile ul > li')
                rankings = []
                for item in items[:100]:
                    try:
                        entry = await self._parse_item(item)
                        if entry:
                            # 장르별 랭킹은 장르를 URL의 카테고리로 설정
                            if genre_key and not entry['genre']:
                                entry['genre'] = genre_key
                            rankings.append(entry)
                    except Exception:
                        continue

                self.logger.info(f"   ✅ [{label}]: {len(rankings)}개 작품")
                self.genre_results[genre_key] = rankings

                # 종합 랭킹은 all_rankings에 포함 (기존 호환)
                if genre_key == '':
                    all_rankings = rankings

            # 장르 수집: 종합 랭킹 작품만 (장르별은 이미 장르 확정)
            await self._fill_genres(browser, all_rankings)

            return all_rankings

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

    async def _fill_genres(self, browser: Browser, rankings: List[Dict[str, Any]]):
        """
        장르가 없는 작품에 대해 개별 페이지에서 장르 수집 후 캐시

        - works 테이블에 이미 장르가 있으면 캐시에서 가져옴
        - 없으면 개별 작품 페이지의 JSON-LD에서 category 추출
        """
        # 1. 캐시된 장르 로드
        genre_cache = get_works_genres(self.platform_id)
        need_fetch = []

        for item in rankings:
            title = item['title']
            if title in genre_cache:
                item['genre'] = genre_cache[title]
            elif item['url']:
                need_fetch.append(item)

        if not need_fetch:
            self.logger.info(f"   📚 장르: 전부 캐시 적중 ({len(rankings)}개)")
            return

        self.logger.info(f"   📚 장르 수집: {len(need_fetch)}개 작품 페이지 방문 필요")

        # 2. 개별 페이지 방문하여 장르 추출
        page = await browser.new_page()
        fetched = 0
        try:
            for item in need_fetch:
                try:
                    genre = await self._fetch_genre_from_page(page, item['url'])
                    if genre:
                        item['genre'] = genre
                        save_work_genre(self.platform_id, item['title'], genre)
                        genre_kr = translate_genre(genre)
                        update_rankings_genre(self.platform_id, item['title'], genre, genre_kr)
                        fetched += 1
                except Exception as e:
                    self.logger.warning(f"   장르 수집 실패 ({item['title']}): {e}")
                    continue
        finally:
            await page.close()

        self.logger.info(f"   📚 장르 수집 완료: {fetched}/{len(need_fetch)}개 성공")

    async def save(self, date: str, data: List[Dict[str, Any]]):
        """종합 + 장르별 랭킹 모두 저장"""
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

        # 장르별 랭킹 저장
        for genre_key, rankings in self.genre_results.items():
            if genre_key == '':  # 종합은 위에서 이미 저장
                continue
            genre_name = PiccomaAgent.GENRE_RANKINGS[genre_key]['name']
            save_rankings(date, self.platform_id, rankings, sub_category=genre_key)
            genre_meta = [
                {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
                 'url': item.get('url', ''), 'genre': item.get('genre', ''), 'rank': item.get('rank')}
                for item in rankings if item.get('thumbnail_url')
            ]
            if genre_meta:
                save_works_metadata(self.platform_id, genre_meta, date=date, sub_category=genre_key)
            self.logger.info(f"   💾 [{genre_name}]: {len(rankings)}개 저장")

    async def _fetch_genre_from_page(self, page, url: str) -> str:
        """개별 작품 페이지에서 BreadcrumbList의 position 2(장르)를 추출"""
        await page.goto(url, wait_until='domcontentloaded', timeout=15000)

        genre = await page.evaluate('''
            () => {
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                for (const s of scripts) {
                    try {
                        const data = JSON.parse(s.textContent);
                        if (data["@type"] === "BreadCrumbList" && data.itemListElement) {
                            for (const item of data.itemListElement) {
                                if (item.position === 2) return item.name;
                            }
                        }
                    } catch(e) {}
                }
                return "";
            }
        ''')
        return genre or ''


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
