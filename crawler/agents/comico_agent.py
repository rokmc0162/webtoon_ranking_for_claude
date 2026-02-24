"""
코미코 (comico) 크롤러 에이전트

특징:
- CSR 방식 (Playwright 필수, Vue.js SPA)
- IP 제한 없음
- 데일리 랭킹 기본, 장르 탭 전환 가능
- 셀렉터: div.thumbnail 구조 (순위+제목+작가)
- 장르별 랭킹: ?currentItemCode= 파라미터
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class ComicoAgent(CrawlerAgent):
    """코미코 데일리 랭킹 크롤러 에이전트"""

    GENRE_RANKINGS = {
        '': {'name': '종합(데일리)', 'code': ''},
        'ファンタジー': {'name': '판타지', 'code': 'fantasy'},
        '恋愛': {'name': '연애', 'code': 'romance'},
        'BL': {'name': 'BL', 'code': 'bl'},
        'ドラマ': {'name': '드라마', 'code': 'drama'},
        '日常': {'name': '일상', 'code': 'daily_life'},
        'TL': {'name': 'TL', 'code': 'tl'},
        'アクション': {'name': '액션', 'code': 'action'},
        '学園': {'name': '학원', 'code': 'school'},
        'ミステリー': {'name': '미스터리', 'code': 'mystery'},
        'ホラー': {'name': '호러', 'code': 'horror'},
    }

    def __init__(self):
        super().__init__(
            platform_id='comico',
            platform_name='코미코 (데일리)',
            url='https://www.comico.jp/menu/all_comic/ranking'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """코미코 종합 + 장르별 랭킹 크롤링"""
        page = await browser.new_page()
        all_rankings = []

        try:
            for genre_key, genre_info in self.GENRE_RANKINGS.items():
                label = genre_info['name']
                code = genre_info['code']

                if code:
                    url = f'{self.url}?currentItemCode={code}'
                else:
                    url = self.url

                self.logger.info(f"📱 코미코 [{label}] 크롤링 중... → {url}")

                await page.goto(url, wait_until='domcontentloaded', timeout=20000)
                await page.wait_for_timeout(5000)

                # DOM 기반 파싱 (썸네일 포함)
                rankings = await self._parse_dom_rankings(page, genre_key)

                self.genre_results[genre_key] = rankings
                self.logger.info(f"   ✅ [{label}]: {len(rankings)}개 작품")

                if genre_key == '':
                    all_rankings = rankings

            return all_rankings

        finally:
            await page.close()

    async def _parse_dom_rankings(self, page, genre_key: str) -> List[Dict[str, Any]]:
        """DOM에서 랭킹 아이템 + 썸네일 추출"""
        items = await page.evaluate("""() => {
            const results = [];
            // comico: li 안에 a > div.thumbnail > figure > img 구조
            const listItems = document.querySelectorAll('li');
            let rank = 0;

            for (const li of listItems) {
                const img = li.querySelector('div.thumbnail img, figure img');
                const captionEl = li.querySelector('div.caption, div.title, a');
                if (!img || !captionEl) continue;

                const src = img.getAttribute('src') || '';
                const alt = img.getAttribute('alt') || '';
                // comico 이미지는 images.comico.io 도메인
                if (!src.includes('comico')) continue;

                const titleEl = li.querySelector('div.caption h2, div.caption p, div.title');
                const title = titleEl ? titleEl.textContent.trim() : alt;
                if (!title || title.length < 2) continue;

                const linkEl = li.querySelector('a[href*="/comic/"]');
                const href = linkEl ? linkEl.getAttribute('href') : '';
                const fullUrl = href ? (href.startsWith('http') ? href : 'https://www.comico.jp' + href) : '';

                rank++;
                if (rank <= 100) {
                    results.push({
                        rank: rank,
                        title: title,
                        url: fullUrl || 'https://www.comico.jp/menu/all_comic/ranking',
                        thumbnail_url: src,
                    });
                }
            }
            return results;
        }""")

        rankings = []
        for item in items[:100]:
            rankings.append({
                'rank': item['rank'],
                'title': item['title'],
                'genre': genre_key,
                'url': item.get('url', ''),
                'thumbnail_url': item.get('thumbnail_url', ''),
            })

        # DOM 파싱 실패 시 텍스트 폴백
        if len(rankings) < 5:
            self.logger.info("   DOM 파싱 부족, 텍스트 폴백...")
            body_text = await page.inner_text('body')
            rankings = self._parse_text_rankings(body_text, genre_key)

        return rankings

    def _parse_text_rankings(self, body_text: str, genre_key: str) -> List[Dict[str, Any]]:
        """텍스트에서 랭킹 아이템 추출 (폴백)"""
        lines = [l.strip() for l in body_text.split('\n') if l.strip()]
        rankings = []
        i = 0

        while i < len(lines) and len(rankings) < 100:
            line = lines[i]
            if line.isdigit() and 1 <= int(line) <= 100:
                rank = int(line)
                if i + 1 < len(lines):
                    title = lines[i + 1].strip()
                    if len(title) >= 2 and title not in ['位', '無料', 'New', '次へ']:
                        rankings.append({
                            'rank': rank,
                            'title': title,
                            'genre': genre_key,
                            'url': f'https://www.comico.jp/menu/all_comic/ranking',
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
