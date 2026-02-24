"""
Twitter/X 수집기.
- Yahoo! リアルタイム検索 (search.yahoo.co.jp/realtime) 사용
- Yahoo가 X/Twitter 데이터를 실시간 인덱싱하므로 별도 인증 불필요
- Playwright headless 브라우저 사용
- 세션당 50개 타이틀 제한
"""
import asyncio
import re
import logging
from typing import Optional
from urllib.parse import quote
from playwright.async_api import async_playwright, Browser, Page

from crawler.sns.base_collector import BaseCollector
from crawler.sns.external_db import save_external_metrics_batch

logger = logging.getLogger('crawler.sns.twitter')


class TwitterCollector(BaseCollector):

    def __init__(self, max_titles: int = 50):
        super().__init__(source_name='twitter', rate_limit_delay=4.0)
        self.max_titles = max_titles
        self._collected = 0
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
            self._page = await ctx.new_page()

    async def _close_browser(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None

    async def collect_all(self, works):
        """오버라이드: 브라우저 시작/종료 래핑."""
        try:
            await self._ensure_browser()
            return await super().collect_all(works)
        finally:
            await self._close_browser()

    async def collect_one(self, title: str, platform: str) -> bool:
        if self._collected >= self.max_titles:
            return False

        page = self._page
        if not page:
            return False

        try:
            # Yahoo! リアルタイム検索 (X/Twitter 데이터)
            short_title = title[:40].strip()
            url = f'https://search.yahoo.co.jp/realtime/search?p={quote(short_title)}'

            await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(3)

            raw = await page.evaluate("""() => {
                const body = document.body.innerText;

                // 결과 건수 추출 (「N件」 패턴)
                const countMatch = body.match(/([\d,]+)件/);
                const resultCount = countMatch
                    ? countMatch[1].replace(/,/g, '')
                    : '0';

                // 트윗 요소 카운트
                const tweets = document.querySelectorAll('article, [class*="tweet"]');

                return {
                    result_count: resultCount,
                    tweet_count: tweets.length,
                };
            }""")

            result_count = int(raw.get('result_count', '0') or '0')
            tweet_count = raw.get('tweet_count', 0)

            if result_count == 0 and tweet_count == 0:
                return False

            metrics = {}
            if result_count > 0:
                metrics['mention_count'] = result_count
            if tweet_count > 0:
                metrics['tweet_count'] = tweet_count

            if metrics:
                save_external_metrics_batch(title, 'twitter', metrics)
                self._collected += 1
                return True

            return False

        except Exception as e:
            logger.warning(f"Twitter/Yahoo search error for '{title[:30]}': {e}")
            return False
