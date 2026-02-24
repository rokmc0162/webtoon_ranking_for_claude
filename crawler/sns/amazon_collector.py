"""
Amazon Japan (amazon.co.jp) Kindle 만화 베스트셀러 수집기.
- Playwright로 베스트셀러 카테고리 페이지 스크래핑
- 안티봇 대응: 랜덤 딜레이(5-15초), webdriver 플래그 제거
- 인증 불필요
"""
import asyncio
import random
import logging
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Browser, Page

from crawler.sns.base_collector import BaseCollector
from crawler.sns.title_matcher import best_match
from crawler.sns.external_db import (
    save_external_id, save_external_metrics_batch
)

logger = logging.getLogger('crawler.sns.amazon_jp')

# Kindle 만화 베스트셀러 카테고리
BESTSELLER_URLS = [
    'https://www.amazon.co.jp/gp/bestsellers/digital-text/2293143051',  # Kindle 만화
]


class AmazonCollector(BaseCollector):

    def __init__(self, max_pages: int = 3):
        super().__init__(source_name='amazon_jp', rate_limit_delay=8.0)
        self.max_pages = max_pages
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    async def _ensure_browser(self):
        if self._browser is None:
            pw = await async_playwright().start()
            self._browser = await pw.chromium.launch(headless=True)
            ctx = await self._browser.new_context(
                locale='ja-JP',
                viewport={'width': 1366, 'height': 768},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36',
            )
            # webdriver 플래그 제거
            page = await ctx.new_page()
            await page.add_init_script('''
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            ''')
            self._page = page

    async def _close_browser(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None

    async def collect_all(self, works: List[Dict[str, str]]) -> Dict[str, int]:
        """오버라이드: 베스트셀러 페이지 스크래핑 → 매칭."""
        self.logger.info(f"[amazon_jp] {len(works)}개 작품 수집 시작")

        try:
            await self._ensure_browser()

            # Phase 1: Amazon 베스트셀러 스크래핑
            amazon_items = await self._scrape_bestsellers()
            self.logger.info(f"[amazon_jp] 베스트셀러에서 {len(amazon_items)}개 작품 수집")

            if not amazon_items:
                return {'success': 0, 'failed': 0, 'skipped': len(works)}

            # Phase 2: 우리 작품과 매칭
            seen = set()
            for work in works:
                title = work['title']
                if title in seen:
                    continue
                seen.add(title)

                matched = best_match(title, amazon_items, threshold=0.65)

                if matched:
                    item, score = matched
                    save_external_id(
                        platform=work['platform'],
                        title=title,
                        source='amazon_jp',
                        external_id=item.get('asin', ''),
                        external_title=item.get('title', ''),
                        match_score=score
                    )
                    metrics = {}
                    if item.get('rank') is not None:
                        metrics['amazon_rank'] = item['rank']
                    if item.get('rating') is not None:
                        metrics['amazon_rating'] = item['rating']
                    if item.get('review_count') is not None:
                        metrics['amazon_review_count'] = item['review_count']

                    if metrics:
                        save_external_metrics_batch(title, 'amazon_jp', metrics)
                        self.success_count += 1
                    else:
                        self.skip_count += 1
                else:
                    self.skip_count += 1

        except Exception as e:
            self.logger.warning(f"[amazon_jp] Error: {e}")
            self.fail_count += 1
        finally:
            await self._close_browser()

        result = {
            'success': self.success_count,
            'failed': self.fail_count,
            'skipped': self.skip_count,
        }
        self.logger.info(f"[amazon_jp] 완료: {result}")
        return result

    async def _scrape_bestsellers(self) -> List[Dict]:
        """Amazon 베스트셀러 페이지에서 작품 목록 스크래핑."""
        page = self._page
        if not page:
            return []

        all_items = []

        for url in BESTSELLER_URLS:
            for page_num in range(1, self.max_pages + 1):
                try:
                    page_url = url if page_num == 1 else f'{url}/ref=zg_bs_pg_{page_num}'
                    await page.goto(page_url, wait_until='domcontentloaded', timeout=20000)
                    await asyncio.sleep(random.uniform(3, 6))

                    items = await page.evaluate('''() => {
                        const results = [];
                        const cards = document.querySelectorAll(
                            '[data-asin], .zg-item-immersion, .a-list-item'
                        );

                        cards.forEach((card, idx) => {
                            const titleEl = card.querySelector(
                                '.zg-text-center-align, ._cDEzb_p13n-sc-css-line-clamp-1, ' +
                                '.p13n-sc-truncate, [class*="truncate"], a.a-link-normal > span'
                            );
                            const ratingEl = card.querySelector(
                                '.a-icon-alt, [class*="a-star"]'
                            );
                            const reviewEl = card.querySelector(
                                '.a-size-small .a-link-normal, [class*="review"]'
                            );
                            const rankEl = card.querySelector(
                                '.zg-badge-text, [class*="badge"]'
                            );

                            const asin = card.getAttribute('data-asin') || '';
                            const title = titleEl ? titleEl.textContent.trim() : '';

                            if (!title) return;

                            let rating = null;
                            if (ratingEl) {
                                const m = ratingEl.textContent.match(/([\d.]+)/);
                                if (m) rating = parseFloat(m[1]);
                            }

                            let reviewCount = null;
                            if (reviewEl) {
                                const m = reviewEl.textContent.replace(/,/g, '').match(/(\d+)/);
                                if (m) reviewCount = parseInt(m[1]);
                            }

                            let rank = null;
                            if (rankEl) {
                                const m = rankEl.textContent.replace(/[#,]/g, '').match(/(\d+)/);
                                if (m) rank = parseInt(m[1]);
                            }
                            if (rank === null) rank = idx + 1;

                            results.push({
                                title, asin, rating, review_count: reviewCount,
                                rank: rank + (results.length > 0 ? 0 : 0),
                            });
                        });

                        return results;
                    }''')

                    # 랭크 보정 (페이지 번호 반영)
                    offset = (page_num - 1) * 50
                    for item in items:
                        if item.get('rank'):
                            item['rank'] += offset
                    all_items.extend(items)

                    self.logger.info(
                        f"  Amazon page {page_num}: {len(items)} items"
                    )

                    # 다음 페이지 전에 랜덤 대기
                    await asyncio.sleep(random.uniform(5, 10))

                except Exception as e:
                    logger.warning(f"Amazon page {page_num} error: {e}")
                    break  # CAPTCHA/블록 시 중단

        return all_items

    async def collect_one(self, title: str, platform: str) -> bool:
        """개별 수집 (collect_all에서 배치 처리하므로 보통 사용 안 함)."""
        return False
