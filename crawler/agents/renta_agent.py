"""
렌타 (Renta!) 크롤러 에이전트

특징:
- SSR 방식 (HTML 직접 렌더링)
- IP 제한 없음
- img.c-contents_cover 셀렉터로 썸네일 추출
- lazyload → data-src에 실제 URL
- 장르별 랭킹: 같은 페이지(ranking_c.htm)에 섹션별로 나뉨 (h2 + swiper)
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class RentaAgent(CrawlerAgent):
    """렌타 마이너치 랭킹 크롤러 에이전트"""

    # 장르별 랭킹 매핑
    # 같은 ranking_c.htm 페이지 내에 h2 섹션으로 구분됨
    # section_id: 페이지 내 <section> 또는 <div> id
    GENRE_RANKINGS = {
        '': {'name': '종합', 'path': '/renta/sc/frm/page/ranking_c.htm'},
        'タテコミ': {'name': '타테코미(웹툰)', 'section_keyword': 'タテコミ'},
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
            self.logger.info(f"📱 렌타 [종합] 크롤링 중... → {self.url}")

            await page.goto(self.url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(5000)

            # DOM 기반 추출 (썸네일 포함)
            rankings = await self._extract_via_dom(page)

            # 폴백: JS evaluate
            if len(rankings) < 10:
                self.logger.info("   DOM 파싱 부족, JS evaluate 시도...")
                rankings = await self._extract_via_js(page)

            all_rankings = rankings[:100]
            self.genre_results[''] = all_rankings
            self.logger.info(f"   ✅ [종합]: {len(all_rankings)}개 작품")

            # ===== タテコミ 섹션 크롤링 =====
            self.logger.info(f"📱 렌타 [タテコミ] 크롤링 중...")
            tatekomi_rankings = await self._extract_section(page, 'タテコミ')

            if len(tatekomi_rankings) < 5:
                # 폴백: タテコミ 섹션으로 스크롤 후 재시도
                self.logger.info("   タテコミ 섹션 스크롤 후 재시도...")
                try:
                    await page.evaluate("""() => {
                        const h2 = Array.from(document.querySelectorAll('h2'))
                            .find(h => h.textContent.includes('タテコミ'));
                        if (h2) h2.scrollIntoView({behavior: 'instant'});
                    }""")
                    await page.wait_for_timeout(3000)
                    tatekomi_rankings = await self._extract_section(page, 'タテコミ')
                except Exception:
                    pass

            self.genre_results['タテコミ'] = tatekomi_rankings[:100]
            self.logger.info(f"   ✅ [タテコミ]: {len(tatekomi_rankings)}개 작품")

            return all_rankings

        finally:
            await page.close()
            await ctx.close()

    async def _extract_section(self, page, section_keyword: str) -> List[Dict[str, Any]]:
        """특정 장르 섹션(h2 기준)에서 작품 추출"""
        items = await page.evaluate("""(keyword) => {
            const results = [];

            // h2 태그에서 해당 장르 섹션 찾기
            const allH2 = document.querySelectorAll('h2');
            let targetH2 = null;
            for (const h2 of allH2) {
                if (h2.textContent.includes(keyword + ' ランキング') ||
                    h2.textContent.includes(keyword + 'ランキング') ||
                    h2.textContent.trim().startsWith(keyword)) {
                    targetH2 = h2;
                    break;
                }
            }

            if (!targetH2) return results;

            // h2의 부모 section 또는 가까운 컨테이너에서 작품 찾기
            // 구조: section > div.c-innerwrap_side > h2 + div(swiper)
            const section = targetH2.closest('section') || targetH2.parentElement;
            if (!section) return results;

            // section 내의 모든 li.swiper-slide에서 작품 추출
            const slides = section.querySelectorAll('li.swiper-slide, li');
            let rank = 0;

            for (const li of slides) {
                const img = li.querySelector('img.c-contents_cover, img[class*="cover"], img[data-src]');
                if (!img) continue;

                const src = img.getAttribute('data-src') || img.getAttribute('src') || '';
                if (!src || src.includes('space.gif') || src.includes('blank') || src.includes('icon')) continue;

                const alt = img.getAttribute('alt') || '';
                let title = alt.replace(/の表紙$/, '').trim();

                if (!title || title.length < 2) {
                    const a = li.querySelector('a[href*="/frm/item/"]');
                    if (a) title = a.textContent.trim();
                }
                if (!title || title.length < 2) continue;

                const linkEl = li.querySelector('a[href*="/frm/item/"]');
                const href = linkEl ? linkEl.getAttribute('href') : '';
                const fullUrl = href ? (href.startsWith('http') ? href : 'https://renta.papy.co.jp' + href) : '';

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
        }""", section_keyword)

        return [
            {
                'rank': item['rank'],
                'title': item['title'],
                'genre': section_keyword,
                'url': item.get('url', ''),
                'thumbnail_url': item.get('thumbnail_url', ''),
            }
            for item in items[:100]
        ]

    async def _extract_via_dom(self, page) -> List[Dict[str, Any]]:
        """DOM에서 직접 추출 (img.c-contents_cover 사용)"""
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
