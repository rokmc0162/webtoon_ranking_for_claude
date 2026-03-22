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
        """레진코믹스 종합 + 장르별 랭킹 크롤링 - API 직접 호출"""
        page = await browser.new_page()
        all_rankings = []

        try:
            # 먼저 페이지 로드 (쿠키/세션 확보)
            await page.goto(self.url, wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_timeout(3000)

            # 장르 목록 API 호출해서 hash_id 매핑
            genre_map = await page.evaluate("""async () => {
                try {
                    const resp = await fetch('/api/genres?type=genre_rank');
                    if (!resp.ok) return null;
                    const data = await resp.json();
                    return data?.results?.data || null;
                } catch(e) {
                    return null;
                }
            }""")

            # hash_id 매핑 구성
            hash_map = {}
            if genre_map:
                for g in genre_map:
                    hash_map[g.get('name', '')] = g.get('hash_id', '')
                self.logger.info(f"   장르 API: {len(genre_map)}개 장르 확인")

            for genre_key, genre_info in self.GENRE_RANKINGS.items():
                label = genre_info['name']
                tab_text = genre_info['tab']

                self.logger.info(f"📱 레진코믹스 [{label}] 크롤링 중...")

                try:
                    # API에서 해당 장르의 hash_id 찾기
                    genre_hash = ''
                    if not tab_text:
                        # 종합 = 첫 번째 장르
                        genre_hash = hash_map.get('総合', '')
                    else:
                        genre_hash = hash_map.get(tab_text, '')

                    if genre_hash:
                        # API cursor pagination으로 100개 수집
                        rankings = await self._fetch_via_api(page, genre_hash, genre_key)
                    else:
                        self.logger.info(f"   hash_id 없음, 스크롤 폴백...")
                        rankings = await self._crawl_scroll(page, genre_key, tab_text)

                    self.genre_results[genre_key] = rankings
                    self.logger.info(f"   ✅ [{label}]: {len(rankings)}개 작품")
                except Exception as e:
                    self.logger.warning(f"   ⚠️ [{label}] 크롤링 실패: {e}")
                    self.genre_results[genre_key] = []
                    continue

                if genre_key == '':
                    all_rankings = rankings

            return all_rankings

        finally:
            await page.close()

    async def _fetch_via_api(self, page, genre_hash: str, genre_key: str) -> List[Dict[str, Any]]:
        """레진 API cursor pagination으로 100개 수집"""
        all_items = await page.evaluate("""async (args) => {
            const [genreHash, maxItems] = args;
            const results = [];
            let cursor = '';

            for (let i = 0; i < 10; i++) {
                try {
                    let url = '/api/ranking?genre_hash_id=' + genreHash + '&type=daily';
                    if (cursor) url += '&cursor=' + cursor;

                    const resp = await fetch(url);
                    if (!resp.ok) break;
                    const data = await resp.json();

                    const items = data?.results?.data || [];
                    if (items.length === 0) break;

                    for (const item of items) {
                        const comic = item.comic || {};
                        results.push({
                            rank: item.rank || (results.length + 1),
                            title: comic.name || '',
                            url: comic.id ? ('https://lezhin.jp/comic/' + comic.id) : '',
                            thumbnail_url: comic.cover_thumbnail_url || '',
                        });
                    }

                    // 다음 페이지 cursor (pagination.next에 위치)
                    const pagination = data?.results?.pagination || {};
                    cursor = pagination.next || '';
                    const hasMore = pagination.has_more_pages;
                    if (!cursor || !hasMore || results.length >= maxItems) break;
                } catch(e) {
                    break;
                }
            }
            return results;
        }""", [genre_hash, 100])

        return [
            {
                'rank': item['rank'],
                'title': item['title'],
                'genre': genre_key if genre_key else '総合',
                'url': item.get('url', ''),
                'thumbnail_url': item.get('thumbnail_url', ''),
            }
            for item in all_items[:100]
        ]

    async def _crawl_scroll(self, page, genre_key: str, tab_text: str) -> List[Dict[str, Any]]:
        """스크롤 기반 폴백 (API 실패 시)"""
        await page.goto(self.url, wait_until='domcontentloaded', timeout=20000)
        await page.wait_for_timeout(5000)

        if tab_text:
            try:
                tab = await page.query_selector(f'text="{tab_text}"')
                if tab:
                    await tab.click()
                    await page.wait_for_timeout(3000)
            except Exception:
                pass

        for _ in range(15):
            await page.evaluate('window.scrollBy(0, 1000)')
            await page.wait_for_timeout(800)

        body_text = await page.inner_text('body')
        rankings = self._parse_text_rankings(body_text, genre_key)

        thumb_items = await self._parse_dom_rankings(page, genre_key)
        for i, r in enumerate(rankings):
            if i < len(thumb_items) and thumb_items[i].get('thumbnail_url'):
                r['thumbnail_url'] = thumb_items[i]['thumbnail_url']
                if thumb_items[i].get('url'):
                    r['url'] = thumb_items[i]['url']

        return rankings

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
                'genre': genre_key if genre_key else '総合',
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
                        genre = genre_key if genre_key else '総合'
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
            genre_meta = [
                {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
                 'url': item.get('url', ''), 'genre': item.get('genre', ''), 'rank': item.get('rank')}
                for item in rankings if item.get('thumbnail_url')
            ]
            if genre_meta:
                save_works_metadata(self.platform_id, genre_meta, date=date, sub_category=genre_key)
            self.logger.info(f"   💾 [{genre_name}]: {len(rankings)}개 저장")
