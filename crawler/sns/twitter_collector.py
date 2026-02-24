"""
Twitter/X 수집기.
- Playwright로 x.com 검색, GraphQL 응답 가로채기
- 인증 불필요 (게스트 검색)
- 세션당 50개 타이틀 제한
"""
import asyncio
import json
import logging
from typing import List, Dict, Optional
from urllib.parse import quote
from playwright.async_api import async_playwright, Browser, Page, Response

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
        self._captured_data: List[Dict] = []

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
            # x.com 검색 결과 페이지로 이동
            query = f'{title[:40]} manga'
            search_url = f'https://x.com/search?q={quote(query)}&src=typed_query&f=live'

            # GraphQL 응답 캡처 설정
            self._captured_data = []

            async def capture_response(response: Response):
                try:
                    url = response.url
                    if 'SearchTimeline' in url or 'search' in url.lower():
                        if response.status == 200:
                            ct = response.headers.get('content-type', '')
                            if 'json' in ct:
                                data = await response.json()
                                self._captured_data.append(data)
                except Exception:
                    pass

            page.on('response', capture_response)

            await page.goto(search_url, wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(4)

            page.remove_listener('response', capture_response)

            # GraphQL 데이터에서 트윗 메트릭 추출
            metrics = self._extract_metrics(self._captured_data)

            # GraphQL이 안 되면 DOM에서 직접 추출 시도
            if not metrics:
                metrics = await self._extract_from_dom(page)

            if not metrics:
                return False

            save_external_metrics_batch(title, 'twitter', metrics)
            self._collected += 1
            return True

        except Exception as e:
            logger.warning(f"Twitter search error for '{title[:30]}': {e}")
            return False

    def _extract_metrics(self, data_list: List[Dict]) -> dict:
        """GraphQL 응답에서 트윗 메트릭 추출."""
        tweet_count = 0
        total_likes = 0
        total_retweets = 0

        for data in data_list:
            tweets = self._find_tweets_in_json(data)
            for tweet in tweets:
                tweet_count += 1
                total_likes += tweet.get('favorite_count', 0)
                total_retweets += tweet.get('retweet_count', 0)

        if tweet_count == 0:
            return {}

        return {
            'tweet_count': tweet_count,
            'total_likes': total_likes,
            'total_retweets': total_retweets,
        }

    def _find_tweets_in_json(self, obj, depth=0) -> List[Dict]:
        """JSON에서 재귀적으로 트윗 데이터 찾기."""
        if depth > 15:
            return []

        tweets = []

        if isinstance(obj, dict):
            # legacy tweet format
            if 'favorite_count' in obj and 'retweet_count' in obj:
                tweets.append({
                    'favorite_count': obj.get('favorite_count', 0),
                    'retweet_count': obj.get('retweet_count', 0),
                })
            else:
                for v in obj.values():
                    tweets.extend(self._find_tweets_in_json(v, depth + 1))
        elif isinstance(obj, list):
            for item in obj[:50]:  # 리스트 크기 제한
                tweets.extend(self._find_tweets_in_json(item, depth + 1))

        return tweets

    async def _extract_from_dom(self, page: Page) -> dict:
        """DOM에서 직접 트윗 정보 추출 (폴백)."""
        try:
            result = await page.evaluate('''() => {
                const articles = document.querySelectorAll('article[data-testid="tweet"]');
                let tweetCount = articles.length;
                let totalLikes = 0;
                let totalRetweets = 0;

                articles.forEach(article => {
                    // 좋아요 수
                    const likeBtn = article.querySelector('[data-testid="like"] span, [data-testid="unlike"] span');
                    if (likeBtn) {
                        const text = likeBtn.textContent.replace(/,/g, '');
                        const n = parseInt(text);
                        if (!isNaN(n)) totalLikes += n;
                    }
                    // RT 수
                    const rtBtn = article.querySelector('[data-testid="retweet"] span, [data-testid="unretweet"] span');
                    if (rtBtn) {
                        const text = rtBtn.textContent.replace(/,/g, '');
                        const n = parseInt(text);
                        if (!isNaN(n)) totalRetweets += n;
                    }
                });

                return { tweetCount, totalLikes, totalRetweets };
            }''')

            if result.get('tweetCount', 0) > 0:
                return {
                    'tweet_count': result['tweetCount'],
                    'total_likes': result['totalLikes'],
                    'total_retweets': result['totalRetweets'],
                }
        except Exception:
            pass

        return {}
