"""
Reddit r/manga 수집기.
- PRAW 라이브러리 사용 (동기식 → run_in_executor 래핑)
- 무료 Reddit API (100 req/min)
- r/manga에서 작품명 검색 → 토론 수, 업보트, 댓글 집계
"""
import asyncio
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

try:
    import praw
    HAS_PRAW = True
except ImportError:
    HAS_PRAW = False

from crawler.sns.base_collector import BaseCollector
from crawler.sns.external_db import save_external_metrics_batch

project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / '.env')
load_dotenv(project_root / 'dashboard-next' / '.env.local')

logger = logging.getLogger('crawler.sns.reddit')


class RedditCollector(BaseCollector):

    def __init__(self):
        super().__init__(source_name='reddit', rate_limit_delay=0.6)

        if not HAS_PRAW:
            logger.warning("praw 미설치. pip install praw")
            self._available = False
            self._reddit = None
            return

        client_id = os.environ.get('REDDIT_CLIENT_ID', '')
        client_secret = os.environ.get('REDDIT_CLIENT_SECRET', '')

        if not client_id or not client_secret:
            logger.warning("REDDIT_CLIENT_ID/SECRET 미설정, 스킵")
            self._available = False
            self._reddit = None
            return

        self._available = True
        self._reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent='webtoon-ranking-bot/1.0 (by jp-webtoon-ranking)'
        )

    async def collect_one(self, title: str, platform: str) -> bool:
        if not self._available:
            return False

        results = await asyncio.get_event_loop().run_in_executor(
            None, self._search_manga, title
        )

        if not results:
            return False

        save_external_metrics_batch(title, 'reddit', results)
        return True

    def _search_manga(self, title: str) -> dict:
        """r/manga에서 작품 검색, 포스트 집계."""
        try:
            subreddit = self._reddit.subreddit('manga')
            # 일본어 제목과 영어 제목 모두 검색
            posts = list(subreddit.search(
                title[:80], sort='relevance', time_filter='month', limit=25
            ))

            if not posts:
                return {}

            total_score = sum(p.score for p in posts)
            total_comments = sum(p.num_comments for p in posts)

            return {
                'post_count': len(posts),
                'total_score': total_score,
                'total_comments': total_comments,
            }

        except Exception as e:
            logger.warning(f"Reddit search error for '{title[:30]}': {e}")
            return {}
