"""
BookWalker (bookwalker.jp) 랭킹 수집기.
- Playwright로 월간 만화 랭킹 페이지 스크래핑
- rankingCard DOM 요소에서 타이틀/평점 추출
- 인증/API 키 불필요
"""
import asyncio
import re
import logging
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Browser, Page

from crawler.sns.base_collector import BaseCollector
from crawler.sns.title_matcher import best_match
from crawler.sns.external_db import (
    save_external_id, save_external_metrics_batch
)

logger = logging.getLogger('crawler.sns.bookwalker')

# 만화 카테고리 랭킹
RANKING_URL = 'https://bookwalker.jp/rank/?category_id=2'


def _strip_volume(title: str) -> str:
    """타이틀에서 권수 표기를 제거 (매칭용).
    예: '転生したらスライムだった件（３１）' → '転生したらスライムだった件'
        'BORUTO 11巻' → 'BORUTO'
    """
    # 전각/반각 괄호 + 숫자
    t = re.sub(r'[\s　]*[（(][\d０-９]+[）)][\s　]*$', '', title)
    # '11巻', '第3巻' 등
    t = re.sub(r'[\s　]*第?[\d０-９]+巻[\s　]*$', '', t)
    # ' 3', ' 11' (끝에 숫자만)
    t = re.sub(r'[\s　]+[\d０-９]+[\s　]*$', '', t)
    return t.strip()


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
            await asyncio.sleep(4)

            items = await page.evaluate("""() => {
                const results = [];
                const cards = document.querySelectorAll('.rankingCard');

                cards.forEach((card, idx) => {
                    // 순위 번호
                    const numEl = card.querySelector('.rankingNum, .ranking-no');
                    let rank = idx + 1;
                    if (numEl) {
                        const m = numEl.textContent.match(/\\d+/);
                        if (m) rank = parseInt(m[0]);
                    }

                    // 타이틀: a[href*="/de"] 링크 텍스트
                    const linkEl = card.querySelector('a[href*="/de"]');
                    const title = linkEl ? linkEl.textContent.trim() : '';
                    const url = linkEl ? linkEl.getAttribute('href') || '' : '';

                    // 평점
                    const ratingText = card.textContent;
                    let rating = null;
                    const ratingMatch = ratingText.match(/(\\d+\\.\\d+)/);
                    if (ratingMatch) rating = parseFloat(ratingMatch[1]);

                    if (title && title.length > 2) {
                        results.push({ title, rating, review_count: null, url, rank });
                    }
                });

                // rankingCard가 없으면 fallback: a[href*="/de"] 직접 추출
                if (results.length === 0) {
                    const links = document.querySelectorAll('.rankingMainContents a[href*="/de"]');
                    links.forEach((link, idx) => {
                        const title = link.textContent.trim();
                        if (title && title.length > 2) {
                            results.push({
                                title,
                                rating: null,
                                review_count: null,
                                url: link.getAttribute('href') || '',
                                rank: idx + 1,
                            });
                        }
                    });
                }

                return results;
            }""")

            # 권수 제거 후 중복 제거
            seen_titles = set()
            for item in items:
                stripped = _strip_volume(item['title'])
                if stripped and stripped not in seen_titles:
                    seen_titles.add(stripped)
                    item['title_original'] = item['title']
                    item['title'] = stripped
                    all_items.append(item)

        except Exception as e:
            logger.warning(f"BookWalker scrape error: {e}")

        return all_items

    async def collect_one(self, title: str, platform: str) -> bool:
        """개별 수집 (collect_all에서 배치 처리하므로 보통 사용 안 함)."""
        return False
