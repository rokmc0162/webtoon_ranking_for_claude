"""
코믹시모아 (コミックシーモア) 크롤러 에이전트

특징:
- CSR + TLS 이슈 (Playwright 필수, ignore_https_errors)
- 단일 페이지에 200개 표시, 상위 50개 사용
- IP 제한 없음
- 셀렉터: li.search_result_box (2026년 현재 구조)
- 카테고리별 랭킹: /search/purpose/ranking/{slug}/ 경로로 구분
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class CmoaAgent(CrawlerAgent):
    """코믹시모아 종합 + 카테고리별 랭킹 크롤러 에이전트"""

    # 카테고리별 랭킹 매핑 (URL: /ranking/{slug}/)
    GENRE_RANKINGS = {
        '': {'name': '종합', 'slug': 'all'},
        '少年マンガ': {'name': '소년만화', 'slug': 'boy'},
        '青年マンガ': {'name': '청년만화', 'slug': 'gentle'},
        '少女マンガ': {'name': '소녀만화', 'slug': 'girl'},
        '女性マンガ': {'name': '여성만화', 'slug': 'lady'},
        'BL': {'name': 'BL', 'slug': 'boyslove'},
        'TL': {'name': 'TL', 'slug': 'teenslove'},
        'sexy': {'name': '어덜트', 'slug': 'sexy'},
    }

    def __init__(self):
        super().__init__(
            platform_id='cmoa',
            platform_name='코믹시모아 (종합)',
            url='https://www.cmoa.jp/search/purpose/ranking/all/'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """
        코믹시모아 종합 + 카테고리별 랭킹 크롤링

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
        all_rankings = []

        try:
            for genre_key, genre_info in self.GENRE_RANKINGS.items():
                label = genre_info['name']
                slug = genre_info['slug']
                url = f'https://www.cmoa.jp/search/purpose/ranking/{slug}/'

                self.logger.info(f"📱 코믹시모아 [{label}] 크롤링 중... → {url}")

                await page.goto(url, wait_until='domcontentloaded', timeout=20000)
                await page.wait_for_selector('li.search_result_box', timeout=10000)
                await page.wait_for_timeout(1000)

                items = await page.query_selector_all('li.search_result_box')
                self.logger.info(f"   작품 요소 {len(items)}개 발견")

                rankings = []
                for item in items[:100]:
                    try:
                        entry = await self._parse_item(item)
                        if entry:
                            if genre_key and not entry['genre']:
                                entry['genre'] = genre_key
                            rankings.append(entry)
                    except Exception as e:
                        self.logger.debug(f"작품 파싱 실패: {e}")
                        continue

                rankings.sort(key=lambda x: x['rank'])
                self.genre_results[genre_key] = rankings
                self.logger.info(f"   ✅ [{label}]: {len(rankings)}개 작품")

                if genre_key == '':
                    all_rankings = rankings

            return all_rankings

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
