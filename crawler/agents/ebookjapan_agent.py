"""
이북재팬 (ebookjapan / Yahoo) 크롤러 에이전트

특징:
- SSR+CSR 하이브리드 (Vue.js)
- IP 제한 없음
- img.cover-main__img 셀렉터로 썸네일 추출
- 종합: /ranking/ 페이지에서 "もっと見る" 클릭 + 스크롤
- 장르별: /ranking/details/?genre=xxx 또는 ?tag=xxx (2026 URL 패턴)
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class EbookjapanAgent(CrawlerAgent):
    """이북재팬 일간 랭킹 크롤러 에이전트"""

    GENRE_RANKINGS = {
        '': {'name': '종합', 'url': 'https://ebookjapan.yahoo.co.jp/ranking/'},
        '少女・女性': {'name': '소녀/여성', 'url': 'https://ebookjapan.yahoo.co.jp/ranking/details/?genre=womens'},
        '少年・青年': {'name': '소년/청년', 'url': 'https://ebookjapan.yahoo.co.jp/ranking/details/?genre=mens'},
        'ファンタジー': {'name': '판타지', 'url': 'https://ebookjapan.yahoo.co.jp/ranking/details/?tag=112'},
        'BL': {'name': 'BL', 'url': 'https://ebookjapan.yahoo.co.jp/ranking/details/?genre=bl'},
        'TL': {'name': 'TL', 'url': 'https://ebookjapan.yahoo.co.jp/ranking/details/?genre=tl'},
    }

    def __init__(self):
        super().__init__(
            platform_id='ebookjapan',
            platform_name='이북재팬 (ebookjapan)',
            url='https://ebookjapan.yahoo.co.jp/ranking/'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """이북재팬 종합 + 카테고리별 랭킹 크롤링 - DOM 기반"""
        page = await browser.new_page()
        all_rankings = []

        try:
            for genre_key, genre_info in self.GENRE_RANKINGS.items():
                label = genre_info['name']
                url = genre_info['url']

                self.logger.info(f"📱 이북재팬 [{label}] 크롤링 중... → {url}")

                await page.goto(url, wait_until='domcontentloaded', timeout=20000)
                await page.wait_for_timeout(4000)

                # 팝업 닫기 (쿠폰/미션 팝업)
                try:
                    close_btn = await page.query_selector('button:has-text("閉じる")')
                    if close_btn:
                        await close_btn.click()
                        await page.wait_for_timeout(1000)
                except Exception:
                    pass

                # 종합 페이지: "もっと見る" 클릭 + 대량 스크롤로 100개 로드
                if genre_key == '':
                    try:
                        more_btn = await page.query_selector('a:has-text("もっと見る")')
                        if more_btn:
                            await more_btn.click()
                            await page.wait_for_timeout(3000)
                            self.logger.info(f"   もっと見る 클릭 완료")
                    except Exception:
                        pass

                    # 대량 스크롤로 lazy loading 트리거 (100개 이상 로드)
                    prev_count = 0
                    for scroll_i in range(25):
                        await page.evaluate('window.scrollBy(0, 1000)')
                        await page.wait_for_timeout(500)
                        if scroll_i % 5 == 4:
                            curr_count = await page.evaluate("""() => {
                                const imgs = document.querySelectorAll('img.cover-main__img');
                                let c = 0;
                                for (const img of imgs) {
                                    const s = img.getAttribute('src') || '';
                                    if (s.startsWith('http') && !s.includes('loading')) c++;
                                }
                                return c;
                            }""")
                            self.logger.info(f"   스크롤 {scroll_i+1}: {curr_count}개 로드됨")
                            if curr_count >= 100 or (curr_count == prev_count and curr_count > 0):
                                break
                            prev_count = curr_count
                else:
                    # 장르 페이지 (/ranking/details/): 스크롤로 50개 로드
                    prev_count = 0
                    for scroll_i in range(15):
                        await page.evaluate('window.scrollBy(0, 800)')
                        await page.wait_for_timeout(500)
                        if scroll_i % 5 == 4:
                            curr_count = await page.evaluate("""() => {
                                const imgs = document.querySelectorAll('img.cover-main__img');
                                let c = 0;
                                for (const img of imgs) {
                                    const s = img.getAttribute('src') || '';
                                    if (s.startsWith('http') && !s.includes('loading')) c++;
                                }
                                return c;
                            }""")
                            self.logger.info(f"   스크롤 {scroll_i+1}: {curr_count}개 로드됨")
                            if curr_count >= 50 or (curr_count == prev_count and curr_count > 0):
                                break
                            prev_count = curr_count

                # DOM 파싱을 메인으로 사용 (img alt에서 타이틀 + 썸네일)
                rankings = await self._parse_dom_rankings(page, genre_key)

                # DOM 결과가 부족하면 텍스트 파싱 폴백 (종합만)
                if len(rankings) < 5 and genre_key == '':
                    self.logger.info(f"   DOM 부족({len(rankings)}개), 텍스트 폴백...")
                    body_text = await page.inner_text('body')
                    rankings = self._parse_text_rankings(body_text, genre_key)

                self.logger.info(f"   ✅ [{label}]: {len(rankings)}개 작품")

                self.genre_results[genre_key] = rankings
                if genre_key == '':
                    all_rankings = rankings

            return all_rankings

        finally:
            await page.close()

    async def _parse_dom_rankings(self, page, genre_key: str) -> List[Dict[str, Any]]:
        """DOM에서 랭킹 아이템 + 썸네일 추출"""
        items = await page.evaluate("""() => {
            const results = [];
            // ebookjapan: img.cover-main__img (lazy-img 포함)
            // src가 cache2-ebookjapan 도메인이면 실제 썸네일, loading-book-cover.svg면 미로딩
            const imgs = document.querySelectorAll('img.cover-main__img');
            let rank = 0;
            const seenTitles = new Set();

            for (const img of imgs) {
                const src = img.getAttribute('src') || '';
                // 실제 썸네일 URL만 (lazy loading placeholder 스킵)
                if (!src.startsWith('http') || src.includes('loading-book-cover')) continue;

                // 타이틀: alt에서 권수 제거
                let alt = img.getAttribute('alt') || '';
                if (!alt || alt.length < 2) continue;

                // 권수 패턴 제거: "タイトル　１１" → "タイトル"
                // 패턴: 전각숫자, 반각숫자 + 巻, 반각숫자만
                let title = alt
                    .replace(/[\\s　]+[０-９]+$/, '')           // 전각 숫자
                    .replace(/[\\s　]+\\d+巻?$/, '')             // N巻 or N
                    .replace(/[\\s　]*[:：][\\s　]*\\d+$/, '')    // ： N
                    .trim();
                if (!title || title.length < 2) continue;

                // 중복 제거
                if (seenTitles.has(title)) continue;
                seenTitles.add(title);

                // 가장 가까운 a 태그에서 URL 추출
                const container = img.closest('li') || img.closest('div') || img.parentElement;
                const linkEl = container ? container.querySelector('a[href*="/books/"]') || container.querySelector('a') : null;
                const href = linkEl ? linkEl.getAttribute('href') : '';
                const fullUrl = href ? (href.startsWith('http') ? href : 'https://ebookjapan.yahoo.co.jp' + href) : '';

                rank++;
                if (rank <= 100) {
                    results.push({
                        rank: rank,
                        title: title,
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
        """텍스트에서 랭킹 아이템 추출 (폴백)"""
        lines = [l.strip() for l in body_text.split('\n') if l.strip()]
        rankings = []
        in_ranking = False
        rank = 0

        for i, line in enumerate(lines):
            if 'ランキング' in line and ('総合' in line or '少女' in line or
                                        '少年' in line or 'ファンタジー' in line):
                in_ranking = True
                continue
            if not in_ranking:
                continue
            if line == 'もっと見る':
                continue
            if line in ['少女マンガ', '女性マンガ', '青年マンガ', '少年マンガ',
                         'BLコミック', 'TLコミック', 'ラノベ']:
                continue
            if re.match(r'^（\d+）$', line):
                continue
            if len(line) < 3 or line in ['有料', '無料', '前日', '週間', '月間',
                                          '歴代', 'トップ', '総合']:
                continue
            if len(line) >= 3 and not line.startswith('http'):
                rank += 1
                if rank <= 100:
                    rankings.append({
                        'rank': rank,
                        'title': line,
                        'genre': genre_key,
                        'url': 'https://ebookjapan.yahoo.co.jp/ranking/',
                        'thumbnail_url': '',
                    })

        return rankings[:100]

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
