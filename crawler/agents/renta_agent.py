"""
렌타 (Renta!) 크롤러 에이전트

특징:
- SSR 방식 (HTML 직접 렌더링)
- IP 제한 없음
- img.c-contents_cover 셀렉터로 썸네일 추출
- lazyload → data-src에 실제 URL
- 장르별 랭킹: 별도 URL로 접근
  - 종합: /renta/sc/frm/page/ranking_c.htm (li.swiper-slide 기반)
  - タテコミ: /renta/sc/frm/search?sort=rank&span=d&site_type=t (검색 결과 기반)
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class RentaAgent(CrawlerAgent):
    """렌타 마이너치 랭킹 크롤러 에이전트"""

    # 장르별 랭킹 매핑
    GENRE_RANKINGS = {
        '': {
            'name': '종합',
            'url': 'https://renta.papy.co.jp/renta/sc/frm/page/ranking_c.htm',
        },
        'タテコミ': {
            'name': '타테코미(웹툰)',
            'url': 'https://renta.papy.co.jp/renta/sc/frm/search?sort=rank&span=d&site_type=t',
        },
    }

    def __init__(self):
        super().__init__(
            platform_id='renta',
            platform_name='렌타 (Renta!)',
            url='https://renta.papy.co.jp/renta/sc/frm/page/ranking_c.htm'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """렌타 종합 + タテコミ 랭킹 크롤링"""
        ctx = await browser.new_context(
            locale='ja-JP',
            viewport={'width': 1366, 'height': 768},
            ignore_https_errors=True,
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/120.0.0.0 Safari/537.36',
        )
        page = await ctx.new_page()
        all_rankings = []

        try:
            # ===== 종합 랭킹 =====
            genre_url = self.GENRE_RANKINGS['']['url']
            self.logger.info(f"📱 렌타 [종합] 크롤링 중... → {genre_url}")

            await page.goto(genre_url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(5000)

            # DOM 기반 추출 (썸네일 포함)
            rankings = await self._extract_ranking_page(page)

            # 폴백: JS evaluate
            if len(rankings) < 10:
                self.logger.info("   DOM 파싱 부족, JS evaluate 시도...")
                rankings = await self._extract_via_js(page)

            all_rankings = rankings[:100]
            self.genre_results[''] = all_rankings
            self.logger.info(f"   ✅ [종합]: {len(all_rankings)}개 작품")

            # ===== タテコミ 랭킹 (별도 URL) =====
            tatekomi_url = self.GENRE_RANKINGS['タテコミ']['url']
            self.logger.info(f"📱 렌타 [タテコミ] 크롤링 중... → {tatekomi_url}")

            tatekomi_rankings = await self._extract_search_rankings(page, tatekomi_url, 'タテコミ')
            self.genre_results['タテコミ'] = tatekomi_rankings[:100]
            self.logger.info(f"   ✅ [タテコミ]: {len(tatekomi_rankings)}개 작품")

            return all_rankings

        finally:
            await page.close()
            await ctx.close()

    async def _extract_search_rankings(self, page, url: str, genre_key: str) -> List[Dict[str, Any]]:
        """검색 결과 페이지에서 랭킹 추출 (タテコミ 등)

        구조: .list-item_wrap > .desclist-item
        제목: .desclist-title_text
        썸네일: .desclist-cover_link img
        URL: a href
        페이지네이션: 여러 페이지 수집 (최대 4페이지 = 100개)
        """
        all_items = []

        for page_num in range(1, 5):  # 최대 4페이지 (약 25개/페이지)
            page_url = f"{url}&page={page_num}" if page_num > 1 else url

            await page.goto(page_url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(3000)

            items = await page.evaluate("""() => {
                const results = [];
                // 검색 결과 아이템: .desclist-item 또는 유사 컨테이너
                const containers = document.querySelectorAll('.desclist-item, .list-item_wrap .desclist-cover_link');

                // 방법 1: desclist-item 기반
                const descItems = document.querySelectorAll('.desclist-item');
                if (descItems.length > 0) {
                    for (const item of descItems) {
                        const titleEl = item.querySelector('.desclist-title_text, .desclist-title_link');
                        const title = titleEl ? titleEl.textContent.trim() : '';
                        if (!title || title.length < 2) continue;

                        const linkEl = item.querySelector('a[href*="/frm/item/"]');
                        const href = linkEl ? linkEl.getAttribute('href') : '';
                        const fullUrl = href ? (href.startsWith('http') ? href : 'https://renta.papy.co.jp' + href) : '';

                        const imgEl = item.querySelector('img');
                        const imgSrc = imgEl ? (imgEl.getAttribute('data-src') || imgEl.getAttribute('src') || '') : '';
                        const thumbUrl = imgSrc.startsWith('http') ? imgSrc : (imgSrc.startsWith('//') ? 'https:' + imgSrc : '');

                        results.push({ title, url: fullUrl, thumbnail_url: thumbUrl });
                    }
                }

                // 방법 2: img.c-contents_cover 기반 (폴백)
                if (results.length === 0) {
                    const imgs = document.querySelectorAll('img.c-contents_cover, img[class*="cover"]');
                    for (const img of imgs) {
                        const src = img.getAttribute('data-src') || img.getAttribute('src') || '';
                        if (!src || src.includes('space.gif') || src.includes('blank') || src.includes('icon')) continue;

                        const alt = img.getAttribute('alt') || '';
                        let title = alt.replace(/の表紙$/, '').trim();
                        if (!title || title.length < 2) {
                            const container = img.closest('li') || img.closest('div') || img.parentElement;
                            const a = container ? container.querySelector('a[href*="/frm/item/"]') : null;
                            if (a) title = a.textContent.trim();
                        }
                        if (!title || title.length < 2) continue;

                        const container = img.closest('li') || img.closest('div') || img.parentElement;
                        const linkEl = container ? container.querySelector('a[href*="/frm/item/"]') : null;
                        const href = linkEl ? linkEl.getAttribute('href') : '';
                        const fullUrl = href ? (href.startsWith('http') ? href : 'https://renta.papy.co.jp' + href) : '';

                        const thumbUrl = src.startsWith('http') ? src : (src.startsWith('//') ? 'https:' + src : '');

                        results.push({ title, url: fullUrl, thumbnail_url: thumbUrl });
                    }
                }

                return results;
            }""")

            if not items:
                self.logger.info(f"   페이지 {page_num}: 작품 없음, 중단")
                break

            start_rank = len(all_items) + 1
            for i, item in enumerate(items):
                all_items.append({
                    'rank': start_rank + i,
                    'title': item['title'],
                    'genre': genre_key,
                    'url': item.get('url', ''),
                    'thumbnail_url': item.get('thumbnail_url', ''),
                })

            self.logger.info(f"   페이지 {page_num}: {len(items)}개 추출 (누적 {len(all_items)}개)")

            if len(all_items) >= 100:
                break

        return all_items[:100]

    async def _extract_ranking_page(self, page) -> List[Dict[str, Any]]:
        """종합 랭킹 페이지에서 DOM 추출 (img.c-contents_cover 사용)"""
        items = await page.evaluate("""() => {
            const results = [];
            // renta: li.swiper-slide 안에 img.c-contents_cover
            const slides = document.querySelectorAll('li.swiper-slide, li');
            let rank = 0;

            for (const li of slides) {
                const img = li.querySelector('img.c-contents_cover, img[class*="cover"]');
                if (!img) continue;

                const src = img.getAttribute('data-src') || img.getAttribute('src') || '';
                if (!src || src.includes('space.gif') || src.includes('blank')) continue;

                const alt = img.getAttribute('alt') || '';
                // alt: "タイトルの表紙" → タイトル
                let title = alt.replace(/の表紙$/, '').trim();

                // 링크에서 타이틀 추출 시도
                if (!title || title.length < 2) {
                    const a = li.querySelector('a[href*="/frm/item/"]');
                    if (a) title = a.textContent.trim();
                }
                if (!title || title.length < 2) continue;

                const linkEl = li.querySelector('a[href*="/frm/item/"]');
                const href = linkEl ? linkEl.getAttribute('href') : '';
                const fullUrl = href ? (href.startsWith('http') ? href : 'https://renta.papy.co.jp' + href) : 'https://renta.papy.co.jp';

                const thumbUrl = src.startsWith('http') ? src : (src.startsWith('//') ? 'https:' + src : 'https://renta.papy.co.jp' + src);

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

    async def _extract_via_js(self, page) -> List[Dict[str, Any]]:
        """JavaScript evaluate로 직접 추출 (폴백)"""
        items = await page.evaluate("""() => {
            const results = [];
            const sections = document.querySelectorAll('ul');
            let rank = 0;

            sections.forEach(ul => {
                const lis = ul.querySelectorAll('li');
                lis.forEach(li => {
                    const a = li.querySelector('a[href*="/frm/item/"]');
                    if (!a) return;

                    const title = a.textContent.trim();
                    if (!title || title.length < 2) return;

                    const href = a.getAttribute('href') || '';
                    const img = li.querySelector('img');
                    const thumbSrc = img ? (img.getAttribute('data-src') || img.getAttribute('src') || '') : '';

                    rank++;
                    if (rank <= 100) {
                        results.push({
                            rank: rank,
                            title: title,
                            url: href.startsWith('http') ? href : 'https://renta.papy.co.jp' + href,
                            thumbnail_url: thumbSrc.startsWith('http') ? thumbSrc : (thumbSrc.startsWith('/') ? 'https://renta.papy.co.jp' + thumbSrc : ''),
                        });
                    }
                });
            });

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
