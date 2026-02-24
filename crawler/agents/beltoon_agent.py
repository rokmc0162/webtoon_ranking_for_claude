"""
벨툰 (BeLTOON) 크롤러 에이전트

특징:
- CSR 방식 (Next.js + styled-components)
- IP 제한 없음
- 해시된 클래스명 → 구조 기반 셀렉터 사용
- li > div > span > div > img 패턴, image.balcony.studio 도메인
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class BeltoonAgent(CrawlerAgent):
    """벨툰 데일리 랭킹 크롤러 에이전트"""

    GENRE_RANKINGS = {
        '': {'name': '종합(데일리)', 'filter': ''},
    }

    def __init__(self):
        super().__init__(
            platform_id='beltoon',
            platform_name='벨툰 (BeLTOON)',
            url='https://www.beltoon.jp/app/all/ranking'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """벨툰 데일리 랭킹 크롤링"""
        page = await browser.new_page()
        all_rankings = []

        try:
            self.logger.info(f"📱 벨툰 [종합] 크롤링 중... → {self.url}")

            await page.goto(self.url, wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_timeout(5000)

            # 스크롤 다운으로 lazy loading 트리거
            for _ in range(10):
                await page.evaluate('window.scrollBy(0, 1000)')
                await page.wait_for_timeout(500)

            # DOM 기반 파싱 (썸네일 포함)
            rankings = await self._parse_dom_rankings(page)

            # 폴백: 텍스트 기반
            if len(rankings) < 5:
                self.logger.info("   DOM 파싱 부족, 텍스트 폴백...")
                body_text = await page.inner_text('body')
                rankings = self._parse_text_rankings(body_text)

            all_rankings = rankings
            self.genre_results[''] = rankings
            self.logger.info(f"   ✅ [종합]: {len(rankings)}개 작품")

            return all_rankings

        finally:
            await page.close()

    async def _parse_dom_rankings(self, page) -> List[Dict[str, Any]]:
        """DOM에서 랭킹 아이템 + 썸네일 추출"""
        items = await page.evaluate("""() => {
            const results = [];
            // beltoon: styled-components, 구조 기반으로 추출
            // li 안에 img[alt="thumbnail"] + 텍스트 구조
            const allLis = document.querySelectorAll('li');
            let rank = 0;

            for (const li of allLis) {
                const img = li.querySelector('img[alt="thumbnail"], img[src*="balcony.studio"], img[src*="image."]');
                if (!img) continue;

                const src = img.getAttribute('src') || '';
                if (!src || src.includes('logo') || src.includes('icon')) continue;

                // 타이틀: li 내의 텍스트 노드 중 적절한 것 찾기
                // 보통 img 이후에 span 또는 p 로 타이틀이 있음
                let title = '';
                const textEls = li.querySelectorAll('span, p, h3, h4, div');
                for (const el of textEls) {
                    const text = el.textContent.trim();
                    // 숫자만(순위), 조회수(N만), 작가명은 스킵
                    if (text.length >= 3 && text.length <= 100 &&
                        !/^\\d+$/.test(text) &&
                        !/^[\\d.]+만$/.test(text) &&
                        !text.includes('チェック') &&
                        !text.includes('ロマンス') &&
                        !text.includes('BL') &&
                        el.children.length === 0) {
                        title = text;
                        break;
                    }
                }

                if (!title || title.length < 2) continue;

                // URL
                const linkEl = li.querySelector('a');
                const href = linkEl ? linkEl.getAttribute('href') : '';
                const fullUrl = href ? (href.startsWith('http') ? href : 'https://www.beltoon.jp' + href) : '';

                const thumbUrl = src.startsWith('http') ? src : (src.startsWith('/') ? 'https://www.beltoon.jp' + src : '');

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
                'genre': '',
                'url': item.get('url', ''),
                'thumbnail_url': item.get('thumbnail_url', ''),
            }
            for item in items[:100]
        ]

    def _parse_text_rankings(self, body_text: str) -> List[Dict[str, Any]]:
        """텍스트에서 랭킹 아이템 추출 - 폴백"""
        lines = [l.strip() for l in body_text.split('\n') if l.strip()]
        rankings = []

        start_idx = 0
        for i, line in enumerate(lines):
            if line == 'デイリー':
                start_idx = i + 1
                break

        i = start_idx
        while i < len(lines) and len(rankings) < 100:
            line = lines[i]

            if line.isdigit() and 1 <= int(line) <= 100:
                rank = int(line)
                j = i + 1
                while j < len(lines) and lines[j].isdigit():
                    j += 1

                if j < len(lines):
                    title = lines[j].strip()
                    if (len(title) >= 2 and
                            title not in ['チェック解除', '絞り込み', '...', 'ロマンス',
                                          'BL', 'ファンタジー', 'ドラマ', 'GL', '少女マンガ'] and
                            not title.startswith('(')):
                        rankings.append({
                            'rank': rank,
                            'title': title,
                            'genre': '',
                            'url': 'https://www.beltoon.jp/app/all/ranking',
                            'thumbnail_url': '',
                        })
                        i = j + 1
                        continue

            i += 1

        return rankings

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
