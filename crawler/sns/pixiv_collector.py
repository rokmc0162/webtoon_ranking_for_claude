"""
Pixiv 팬아트 수집기.
- pixivpy3 라이브러리 사용 (동기식 → run_in_executor 래핑)
- 작품명 태그로 일러스트 검색 → 팬아트 수/북마크/조회수 집계
- PIXIV_REFRESH_TOKEN 환경변수 필요 (1회 gppt 도구로 발급)
"""
import asyncio
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

try:
    from pixivpy3 import AppPixivAPI
    HAS_PIXIV = True
except ImportError:
    HAS_PIXIV = False

from crawler.sns.base_collector import BaseCollector
from crawler.sns.external_db import save_external_metrics_batch

project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / '.env')
load_dotenv(project_root / 'dashboard-next' / '.env.local')

logger = logging.getLogger('crawler.sns.pixiv')


class PixivCollector(BaseCollector):

    def __init__(self):
        super().__init__(source_name='pixiv', rate_limit_delay=2.0)

        if not HAS_PIXIV:
            logger.warning("pixivpy3 미설치. pip install pixivpy3")
            self._available = False
            self._api = None
            return

        token = os.environ.get('PIXIV_REFRESH_TOKEN', '')
        if not token:
            logger.warning("PIXIV_REFRESH_TOKEN 미설정, 스킵")
            self._available = False
            self._api = None
            return

        try:
            self._api = AppPixivAPI()
            self._api.auth(refresh_token=token)
            self._available = True
        except Exception as e:
            logger.warning(f"Pixiv 인증 실패: {e}")
            self._available = False
            self._api = None

    async def collect_one(self, title: str, platform: str) -> bool:
        if not self._available:
            return False

        results = await asyncio.get_event_loop().run_in_executor(
            None, self._search_fanart, title
        )

        if not results:
            return False

        save_external_metrics_batch(title, 'pixiv', results)
        return True

    def _search_fanart(self, title: str) -> dict:
        """Pixiv에서 작품 태그로 일러스트 검색, 집계."""
        try:
            result = self._api.search_illust(
                word=title[:50],
                search_target='partial_match_for_tags',
                sort='popular_desc',
            )

            illusts = result.get('illusts', [])
            if not illusts:
                return {}

            fanart_count = len(illusts)
            total_bookmarks = sum(i.get('total_bookmarks', 0) for i in illusts)
            total_views = sum(i.get('total_view', 0) for i in illusts)

            return {
                'fanart_count': fanart_count,
                'fanart_bookmarks': total_bookmarks,
                'fanart_views': total_views,
            }

        except Exception as e:
            # 토큰 만료 시 재인증 시도
            if 'Invalid' in str(e) or 'expired' in str(e):
                try:
                    token = os.environ.get('PIXIV_REFRESH_TOKEN', '')
                    self._api.auth(refresh_token=token)
                    return self._search_fanart(title)
                except Exception:
                    pass
            logger.warning(f"Pixiv search error for '{title[:30]}': {e}")
            return {}
