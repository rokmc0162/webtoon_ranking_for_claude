"""
ブッコミ (Handycomic/BookLive Comic) 크롤러 에이전트

특징:
- SSR 방식
- 주간 랭킹: 20위/페이지, 최대 5페이지 (100위)
- 장르: 5개 (총합, 소녀·여성, 소년·청년, TL, BL)
- 제목: a[href*="product"] 내 img[alt]
- 썸네일: res.booklive.jp 도메인
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class HandycomicAgent(CrawlerAgent):
    """ブッコミ (Handycomic) 주간 랭킹 크롤러"""

    GENRE_RANKINGS = {
        '': {'name': '총합', 'path': '/ranking/weekly'},
        '少女・女性': {'name': '소녀·여성', 'path': '/ranking/weekly/category_id/CF'},
        '少年・青年': {'name': '소년·청년', 'path': '/ranking/weekly/category_id/C'},
        'TL': {'name': 'TL', 'path': '/ranking/weekly/category_id/TL'},
        'BL': {'name': 'BL', 'path': '/ranking/weekly/category_id/BL'},
    }

    BASE_URL = 'https://sp.handycomic.jp'
    MAX_PAGES = 5  # 페이지당 20개 × 5페이지 = 100개

    def __init__(self):
        super().__init__(
            platform_id='handycomic',
            platform_name='ブッコミ (Handycomic)',
            url='https://sp.handycomic.jp/ranking/weekly'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """핸디코믹 주간 랭킹 크롤링 (전 장르)"""
        page = await browser.new_page()

        try:
            for genre_key, genre_info in self.GENRE_RANKINGS.items():
                label = genre_info['name']
                base_path = genre_info['path']
                self.logger.info(f"   📖 [{label}] 크롤링...")

                rankings = []
                seen_ids = set()

                for page_no in range(1, self.MAX_PAGES + 1):
                    if page_no == 1:
                        url = f"{self.BASE_URL}{base_path}"
                    else:
                        url = f"{self.BASE_URL}{base_path}/page_no/{page_no}"

                    try:
                        await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                        await page.wait_for_timeout(1500)

                        items = await page.query_selector_all('a[href*="/product/index/title_id/"]')
                        new_count = 0

                        for item in items:
                            entry = await self._parse_item(item, len(rankings) + 1, seen_ids, genre_key)
                            if entry:
                                rankings.append(entry)
                                new_count += 1

                        if new_count == 0:
                            break  # 더 이상 새 아이템 없음

                    except Exception as e:
                        self.logger.warning(f"   ⚠️ [{label}] 페이지 {page_no} 실패: {e}")
                        break

                self.logger.info(f"   ✅ [{label}]: {len(rankings)}개 작품")
                self.genre_results[genre_key] = rankings

        finally:
            await page.close()

        return self.genre_results.get('', [])

    async def _parse_item(self, item, fallback_rank: int, seen_ids: set, genre_key: str) -> Dict[str, Any]:
        """개별 랭킹 아이템 파싱"""
        href = await item.get_attribute('href') or ''

        # title_id 추출 (중복 방지)
        m = re.search(r'title_id/(\d+)', href)
        if not m:
            return None
        title_id = m.group(1)
        if title_id in seen_ids:
            return None
        seen_ids.add(title_id)

        # 이미지가 있는 링크만 처리 (텍스트 링크 스킵)
        img = await item.query_selector('img')
        if not img:
            return None

        # 제목: img alt
        title = await img.get_attribute('alt') or ''
        if not title or len(title) < 2:
            return None

        # 썸네일
        thumbnail_url = await img.get_attribute('src') or ''

        # URL
        url = f"{self.BASE_URL}{href}" if not href.startswith('http') else href

        return {
            'rank': fallback_rank,
            'title': title.strip(),
            'genre': genre_key,
            'url': url,
            'thumbnail_url': thumbnail_url,
        }

    async def save(self, date: str, data: List[Dict[str, Any]]):
        """종합 + 장르별 랭킹 모두 저장"""
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

        for genre_key, rankings in self.genre_results.items():
            if genre_key == '' or not rankings:
                continue
            save_rankings(date, self.platform_id, rankings, sub_category=genre_key)
            genre_meta = [
                {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
                 'url': item.get('url', ''), 'genre': item.get('genre', ''), 'rank': item.get('rank')}
                for item in rankings if item.get('thumbnail_url')
            ]
            if genre_meta:
                save_works_metadata(self.platform_id, genre_meta, date=date, sub_category=genre_key)
