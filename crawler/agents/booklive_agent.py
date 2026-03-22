"""
북라이브 (BookLive) 크롤러 에이전트

특징:
- SSR 방식 (서버 렌더링, 가장 데이터 풍부)
- 100개/페이지, 페이지네이션 있음
- IP 제한 없음
- li.item.clearfix > div.left > div.picture > a > img 구조
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class BookliveAgent(CrawlerAgent):
    """북라이브 일간/종합 랭킹 크롤러 에이전트"""

    GENRE_RANKINGS = {
        '': {'name': '종합', 'path': '/ranking/day'},
        '少年マンガ': {'name': '소년만화', 'path': '/ranking/day/category_id/C/genre_id/6'},
        '青年マンガ': {'name': '청년만화', 'path': '/ranking/day/category_id/C/genre_id/5'},
        '少女マンガ': {'name': '소녀만화', 'path': '/ranking/day/category_id/CF/genre_id/1'},
        '女性マンガ': {'name': '여성만화', 'path': '/ranking/day/category_id/CF/genre_id/2'},
        'BL': {'name': 'BL', 'path': '/ranking/day/category_id/BL/genre_id/3'},
        'TL': {'name': 'TL', 'path': '/ranking/day/category_id/TL/genre_id/7'},
        'ラノベ': {'name': '라노벨', 'path': '/ranking/day/category_id/L/genre_id/14'},
    }

    def __init__(self):
        super().__init__(
            platform_id='booklive',
            platform_name='북라이브 (BookLive)',
            url='https://booklive.jp/ranking/day'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """북라이브 종합 + 장르별 랭킹 크롤링"""
        page = await browser.new_page()
        all_rankings = []

        try:
            for genre_key, genre_info in self.GENRE_RANKINGS.items():
                label = genre_info['name']
                path = genre_info['path']
                url = f'https://booklive.jp{path}'

                try:
                    self.logger.info(f"📱 북라이브 [{label}] 크롤링 중... → {url}")

                    await page.goto(url, wait_until='domcontentloaded', timeout=20000)
                    await page.wait_for_timeout(3000)

                    # DOM 기반 파싱 (썸네일 포함)
                    rankings = await self._parse_dom_rankings(page, genre_key)

                    # 폴백: 텍스트 기반
                    if len(rankings) < 5:
                        self.logger.info("   DOM 파싱 부족, 텍스트 폴백...")
                        body_text = await page.inner_text('body')
                        rankings = self._parse_text_rankings(body_text, genre_key)

                    self.genre_results[genre_key] = rankings
                    self.logger.info(f"   ✅ [{label}]: {len(rankings)}개 작품")

                    if genre_key == '':
                        all_rankings = rankings
                except Exception as e:
                    self.logger.warning(f"   ⚠️ [{label}] 크롤링 실패: {e}")
                    self.genre_results[genre_key] = []

            return all_rankings

        finally:
            await page.close()

    async def _parse_dom_rankings(self, page, genre_key: str) -> List[Dict[str, Any]]:
        """DOM에서 랭킹 아이템 + 썸네일 추출"""
        items = await page.evaluate("""() => {
            const results = [];
            // booklive: ul.search_item_list > li.item > div.left > div.picture > a > img
            // img id: search_image_1, search_image_2, ...
            // img alt에 타이틀 포함
            const listItems = document.querySelectorAll('ul.search_item_list li.item, li.item.clearfix');
            let rank = 0;

            for (const li of listItems) {
                // 썸네일 (div.picture 안의 img)
                const img = li.querySelector('div.picture img, img[id^="search_image"]');
                if (!img) continue;

                const src = img.getAttribute('src') || '';
                if (!src || src.includes('blank') || src.includes('spacer')) continue;

                // 타이틀: img alt 또는 텍스트 요소
                let title = img.getAttribute('alt') || '';
                if (!title || title.length < 2) {
                    const titleEl = li.querySelector('a.product_title, p.title a, h3 a, a[href*="/product/"]');
                    if (titleEl) title = titleEl.textContent.trim();
                }
                if (!title || title.length < 2) continue;

                // URL
                const linkEl = li.querySelector('a[href*="/product/"]');
                const href = linkEl ? linkEl.getAttribute('href') : '';
                const fullUrl = href ? (href.startsWith('http') ? href : 'https://booklive.jp' + href) : '';

                const thumbUrl = src.startsWith('http') ? src : (src.startsWith('//') ? 'https:' + src : '');

                rank++;
                if (rank <= 100) {
                    results.push({
                        rank: rank,
                        title: title,
                        url: fullUrl,
                        thumbnail_url: thumbUrl,
                    });
                }
            }
            return results;
        }""")

        return [
            {
                'rank': item['rank'],
                'title': item['title'],
                'genre': genre_key if genre_key else '総合',
                'url': item.get('url', ''),
                'thumbnail_url': item.get('thumbnail_url', ''),
            }
            for item in items[:100]
        ]

    def _parse_text_rankings(self, body_text: str, genre_key: str) -> List[Dict[str, Any]]:
        """텍스트에서 랭킹 아이템 추출 (N位 패턴) - 폴백"""
        lines = [l.strip() for l in body_text.split('\n') if l.strip()]
        rankings = []

        i = 0
        while i < len(lines) and len(rankings) < 100:
            line = lines[i]
            rank_match = re.match(r'^(\d+)位$', line)
            if rank_match:
                rank = int(rank_match.group(1))
                if i + 1 < len(lines):
                    title = lines[i + 1].strip()
                    if len(title) >= 2 and not title.endswith('位'):
                        genre = genre_key
                        if not genre:
                            for j in range(i + 2, min(i + 6, len(lines))):
                                g = lines[j].strip()
                                if g in ['少年マンガ', '青年マンガ', '少女マンガ',
                                         '女性マンガ', 'BL', 'TL', 'ラノベ']:
                                    genre = g
                                    break
                            if not genre:
                                genre = '総合'

                        rankings.append({
                            'rank': rank,
                            'title': title,
                            'genre': genre,
                            'url': 'https://booklive.jp/ranking/day',
                            'thumbnail_url': '',
                        })
            i += 1

        return rankings

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
