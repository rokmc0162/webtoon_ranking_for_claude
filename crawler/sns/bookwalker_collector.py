"""
BookWalker (bookwalker.jp) 랭킹 수집기.
- Playwright로 월간 만화 랭킹 페이지 스크래핑
- JSON-LD (Schema.org Product) 구조화 데이터 파싱
- 인증/API 키 불필요
"""
import asyncio
import logging
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Browser, Page

from crawler.sns.base_collector import BaseCollector
from crawler.sns.title_matcher import best_match
from crawler.sns.external_db import (
    save_external_id, save_external_metrics_batch
)

logger = logging.getLogger('crawler.sns.bookwalker')

RANKING_URL = 'https://bookwalker.jp/rank/'


class BookWalkerCollector(BaseCollector):

    def __init__(self, max_pages: int = 5):
        super().__init__(source_name='bookwalker', rate_limit_delay=4.0)
        self.max_pages = max_pages
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    async def _ensure_browser(self):
        if self._browser is None:
            pw = await async_playwright().start()
            self._browser = await pw.chromium.launch(headless=True)
            ctx = await self._browser.new_context(
                locale='ja-JP',
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36',
            )
            self._page = await ctx.new_page()

    async def _close_browser(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None

    async def collect_all(self, works: List[Dict[str, str]]) -> Dict[str, int]:
        """오버라이드: 랭킹 페이지 먼저 스크래핑 → 우리 작품과 매칭."""
        self.logger.info(f"[bookwalker] {len(works)}개 작품 수집 시작")

        try:
            await self._ensure_browser()

            # Phase 1: BookWalker 랭킹 스크래핑
            bw_items = await self._scrape_rankings()
            self.logger.info(f"[bookwalker] 랭킹에서 {len(bw_items)}개 작품 수집")

            if not bw_items:
                return {'success': 0, 'failed': 0, 'skipped': len(works)}

            # Phase 2: 우리 작품과 매칭
            seen = set()
            for work in works:
                title = work['title']
                if title in seen:
                    continue
                seen.add(title)

                matched = best_match(
                    title,
                    bw_items,
                    threshold=0.7
                )

                if matched:
                    item, score = matched
                    save_external_id(
                        platform=work['platform'],
                        title=title,
                        source='bookwalker',
                        external_id=item.get('url', ''),
                        external_title=item.get('title', ''),
                        match_score=score
                    )
                    metrics = {}
                    if item.get('rank') is not None:
                        metrics['bw_rank'] = item['rank']
                    if item.get('rating') is not None:
                        metrics['bw_rating'] = item['rating']
                    if item.get('review_count') is not None:
                        metrics['bw_review_count'] = item['review_count']

                    if metrics:
                        save_external_metrics_batch(title, 'bookwalker', metrics)
                        self.success_count += 1
                    else:
                        self.skip_count += 1
                else:
                    self.skip_count += 1

            if self.success_count > 0 or self.skip_count > 0:
                self.logger.info(
                    f"[bookwalker] 매칭 결과: "
                    f"{self.success_count} matched, {self.skip_count} skipped"
                )

        except Exception as e:
            self.logger.warning(f"[bookwalker] Error: {e}")
            self.fail_count += 1
        finally:
            await self._close_browser()

        result = {
            'success': self.success_count,
            'failed': self.fail_count,
            'skipped': self.skip_count,
        }
        self.logger.info(f"[bookwalker] 완료: {result}")
        return result

    async def _scrape_rankings(self) -> List[Dict]:
        """BookWalker 랭킹 페이지에서 작품 목록 스크래핑."""
        page = self._page
        if not page:
            return []

        all_items = []

        try:
            await page.goto(RANKING_URL, wait_until='domcontentloaded', timeout=20000)
            await asyncio.sleep(3)

            # JSON-LD에서 Product 데이터 추출 시도
            items = await page.evaluate('''() => {
                const results = [];

                // JSON-LD 파싱
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                scripts.forEach((s, idx) => {
                    try {
                        const d = JSON.parse(s.textContent);
                        if (d['@type'] === 'Product' || d['@type'] === 'Book') {
                            results.push({
                                title: d.name || '',
                                rating: d.aggregateRating ? parseFloat(d.aggregateRating.ratingValue) : null,
                                review_count: d.aggregateRating ? parseInt(d.aggregateRating.reviewCount) : null,
                                url: d.url || '',
                                rank: idx + 1,
                            });
                        }
                    } catch(e) {}
                });

                // JSON-LD가 없으면 DOM에서 직접 추출
                if (results.length === 0) {
                    const items = document.querySelectorAll('.o-contents-section__body .m-book-item, .ranking-list li, .o-tile, [class*="rank"]');
                    items.forEach((item, idx) => {
                        const titleEl = item.querySelector('a[title], .title, h3, h2, [class*="title"]');
                        const ratingEl = item.querySelector('[class*="rating"], [class*="star"], .score');
                        const linkEl = item.querySelector('a[href*="/de"]');

                        if (titleEl) {
                            results.push({
                                title: titleEl.textContent.trim() || titleEl.getAttribute('title') || '',
                                rating: ratingEl ? parseFloat(ratingEl.textContent) || null : null,
                                review_count: null,
                                url: linkEl ? linkEl.getAttribute('href') || '' : '',
                                rank: idx + 1,
                            });
                        }
                    });
                }

                return results;
            }''')

            all_items.extend(items)

        except Exception as e:
            logger.warning(f"BookWalker scrape error: {e}")

        return all_items

    async def collect_one(self, title: str, platform: str) -> bool:
        """개별 수집 (collect_all에서 배치 처리하므로 보통 사용 안 함)."""
        return False
