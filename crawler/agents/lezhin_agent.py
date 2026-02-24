"""
레진코믹스 (Lezhin) 크롤러 에이전트

특징:
- CSR 방식 (Next.js, React 기반)
- IP 제한 없음
- Tailwind CSS 기반 레이아웃
- div.relative.border img 셀렉터로 썸네일 추출
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class LezhinAgent(CrawlerAgent):
    """레진코믹스 일간 랭킹 크롤러 에이전트"""

    GENRE_RANKINGS = {
        '': {'name': '종합', 'tab': ''},
        '少年マンガ': {'name': '소년만화', 'tab': '少年マンガ'},
        '青年マンガ': {'name': '청년만화', 'tab': '青年マンガ'},
        '少女マンガ': {'name': '소녀만화', 'tab': '少女マンガ'},
        '女性マンガ': {'name': '여성만화', 'tab': '女性マンガ'},
        'BL': {'name': 'BL', 'tab': 'BLコミック'},
        'TL': {'name': 'TL', 'tab': 'TLコミック'},
    }

    def __init__(self):
        super().__init__(
            platform_id='lezhin',
            platform_name='레진코믹스 (Lezhin)',
            url='https://lezhin.jp/ranking'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """레진코믹스 종합 + 장르별 랭킹 크롤링"""
        page = await browser.new_page()
        all_rankings = []

        try:
            for genre_key, genre_info in self.GENRE_RANKINGS.items():
                label = genre_info['name']
                tab_text = genre_info['tab']

                self.logger.info(f"📱 레진코믹스 [{label}] 크롤링 중...")

                await page.goto(self.url, wait_until='domcontentloaded', timeout=20000)
                await page.wait_for_timeout(5000)

                # 장르 탭 클릭 (종합이 아닌 경우)
                if tab_text:
                    try:
                        tab = await page.query_selector(f'text="{tab_text}"')
                        if tab:
                            await tab.click()
                            await page.wait_for_timeout(3000)
                    except Exception:
                        pass

                # 스크롤 다운으로 lazy loading 트리거
                for _ in range(5):
                    await page.evaluate('window.scrollBy(0, 1000)')
                    await page.wait_for_timeout(500)

                # 텍스트 기반 파싱 (타이틀) + DOM 기반 (썸네일 URL)
                body_text = await page.inner_text('body')
                rankings = self._parse_text_rankings(body_text, genre_key)

                # DOM에서 썸네일 URL 매핑
                thumb_items = await self._parse_dom_rankings(page, genre_key)
                for i, r in enumerate(rankings):
                    if i < len(thumb_items) and thumb_items[i].get('thumbnail_url'):
                        r['thumbnail_url'] = thumb_items[i]['thumbnail_url']
                        if thumb_items[i].get('url'):
                            r['url'] = thumb_items[i]['url']

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
            // lezhin: Tailwind CSS. 썸네일 img는 div.relative.border 안에 있음
            // alt="chapter_image", src=contents.lezhin.jp/... 패턴
            // 타이틀은 img 없이 가져올 수 없으므로 이미지 URL만 순서대로 수집
            const imgs = document.querySelectorAll('img.w-full.h-full');
            let rank = 0;

            for (const img of imgs) {
                const src = img.getAttribute('src') || '';
                if (!src.includes('lezhin') && !src.includes('hrsm-tech')) continue;
                if (src.includes('logo') || src.includes('static/media') || src.includes('icon')) continue;

                const parent = img.closest('div.relative');
                if (!parent) continue;

                // 가장 가까운 a 태그에서 URL 추출
                const linkEl = parent.closest('a') || parent.querySelector('a');
                const href = linkEl ? linkEl.getAttribute('href') : '';
                const fullUrl = href ? (href.startsWith('http') ? href : 'https://lezhin.jp' + href) : '';

                rank++;
                if (rank <= 100) {
                    results.push({
                        rank: rank,
                        title: '',
                        url: fullUrl,
                        thumbnail_url: src,
                    });
                }
            }
            return results;
        }""")

        return [
            {
                'rank': item['rank'],
                'title': item['title'],
                'genre': genre_key,
                'url': item.get('url', ''),
                'thumbnail_url': item.get('thumbnail_url', ''),
            }
            for item in items[:100]
        ]

    def _parse_text_rankings(self, body_text: str, genre_key: str) -> List[Dict[str, Any]]:
        """텍스트에서 랭킹 아이템 추출 (N + 位 + 타이틀 패턴) - 폴백"""
        lines = [l.strip() for l in body_text.split('\n') if l.strip()]
        rankings = []

        i = 0
        while i < len(lines) and len(rankings) < 100:
            line = lines[i]
            if (line.isdigit() and 1 <= int(line) <= 100 and
                    i + 1 < len(lines) and lines[i + 1].strip() == '位'):
                rank = int(line)
                if i + 2 < len(lines):
                    title = lines[i + 2].strip()
                    if len(title) >= 2:
                        genre = genre_key
                        if i + 3 < len(lines):
                            meta = lines[i + 3].strip()
                            if '・' in meta:
                                parts = meta.split('・')
                                if len(parts) >= 2:
                                    genre_part = parts[-1].strip()
                                    if ' / ' in genre_part:
                                        genre = genre_part.split(' / ')[0].strip()
                                    else:
                                        genre = genre_part

                        rankings.append({
                            'rank': rank,
                            'title': title,
                            'genre': genre,
                            'url': 'https://lezhin.jp/ranking',
                            'thumbnail_url': '',
                        })
                i += 4
            else:
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
            self.logger.info(f"   💾 [{genre_name}]: {len(rankings)}개 저장")
