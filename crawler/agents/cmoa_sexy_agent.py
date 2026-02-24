"""
코믹시모아 라이트 어덜트 (ライトアダルト) 랭킹 크롤러 에이전트

특징:
- 기존 cmoa_agent와 동일한 DOM 구조
- /search/purpose/ranking/sexy/ 경로 사용
- IP 제한 없음
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class CmoaSexyAgent(CrawlerAgent):
    """코믹시모아 라이트 어덜트(sexy) 랭킹 크롤러 에이전트"""

    def __init__(self):
        super().__init__(
            platform_id='cmoa_sexy',
            platform_name='코믹시모아 (라이트어덜트)',
            url='https://www.cmoa.jp/search/purpose/ranking/sexy/'
        )

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """코믹시모아 라이트 어덜트 랭킹 크롤링"""
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        try:
            self.logger.info(f"📱 코믹시모아 [라이트 어덜트] 크롤링 중... → {self.url}")

            await page.goto(self.url, wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_selector('li.search_result_box', timeout=10000)
            await page.wait_for_timeout(1000)

            items = await page.query_selector_all('li.search_result_box')
            self.logger.info(f"   작품 요소 {len(items)}개 발견")

            rankings = []
            for item in items[:100]:
                try:
                    entry = await self._parse_item(item)
                    if entry:
                        rankings.append(entry)
                except Exception as e:
                    self.logger.debug(f"작품 파싱 실패: {e}")
                    continue

            rankings.sort(key=lambda x: x['rank'])
            self.logger.info(f"   ✅ [라이트 어덜트]: {len(rankings)}개 작품")

            return rankings

        finally:
            await page.close()
            await context.close()

    async def _parse_item(self, item) -> Dict[str, Any]:
        """개별 랭킹 아이템 파싱 (cmoa_agent와 동일 구조)"""

        # 1. 순위
        rank_el = await item.query_selector('.title_rank')
        if not rank_el:
            return None
        rank_text = (await rank_el.inner_text()).strip()
        match = re.search(r'(\d+)位', rank_text)
        if not match:
            return None
        rank = int(match.group(1))

        # 2. 제목
        title = None
        title_el = await item.query_selector('.search_result_box_right_sec1 a.title')
        if title_el:
            title = (await title_el.inner_text()).strip()
        if not title:
            img_el = await item.query_selector('img.volume_img')
            if img_el:
                title = await img_el.get_attribute('alt')
        if not title:
            return None

        # 3. URL
        url = ''
        if title_el:
            href = await title_el.get_attribute('href')
            if href:
                url = f"https://www.cmoa.jp{href}" if not href.startswith('http') else href

        # 4. 장르
        genre = ''
        sec2 = await item.query_selector('.search_result_box_right_sec2')
        if sec2:
            sec2_html = await sec2.inner_html()
            genre_match = re.search(r'ジャンル：\s*<a[^>]*>([^<]+)</a>', sec2_html)
            if genre_match:
                genre = genre_match.group(1).strip()

        # 5. 썸네일
        thumbnail_url = ''
        thumb_el = await item.query_selector('img.volume_img')
        if thumb_el:
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
        """랭킹 저장"""
        from crawler.db import save_rankings, backup_to_json, save_works_metadata

        save_rankings(date, self.platform_id, data, sub_category='')
        works_meta = [
            {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
             'url': item.get('url', ''), 'genre': item.get('genre', ''), 'rank': item.get('rank')}
            for item in data if item.get('thumbnail_url')
        ]
        if works_meta:
            save_works_metadata(self.platform_id, works_meta, date=date, sub_category='')
        backup_to_json(date, self.platform_id, data)
