"""
Jikan (MyAnimeList 비공식) REST API 수집기.
- 무료, API 키 불필요, 60 req/min
- GET https://api.jikan.moe/v4/manga?q={query}
- MAL 점수(1-10), 회원 수, 랭킹, 인기도
"""
import asyncio
import aiohttp
from typing import Optional

from crawler.sns.base_collector import BaseCollector
from crawler.sns.external_db import (
    get_cached_external_id, save_external_id, save_external_metrics_batch
)
from crawler.sns.title_matcher import best_match

JIKAN_BASE = 'https://api.jikan.moe/v4'


class JikanCollector(BaseCollector):

    def __init__(self):
        super().__init__(source_name='mal', rate_limit_delay=1.2)

    async def collect_one(self, title: str, platform: str) -> bool:
        cached_id = get_cached_external_id(title, 'mal')

        async with aiohttp.ClientSession() as session:
            manga = None
            match_score = 1.0

            if cached_id:
                manga = await self._fetch_by_id(session, int(cached_id))
            else:
                candidates = await self._search(session, title)
                if not candidates:
                    return False

                result = best_match(title, candidates, threshold=0.75)
                if not result:
                    return False

                manga, match_score = result
                save_external_id(
                    platform=platform, title=title, source='mal',
                    external_id=str(manga['mal_id']),
                    external_title=manga.get('title_japanese', '') or manga.get('title', ''),
                    match_score=match_score
                )

            if not manga:
                return False

            metrics = {}
            if manga.get('score') is not None:
                metrics['score'] = manga['score']
            if manga.get('members') is not None:
                metrics['members'] = manga['members']
            if manga.get('rank') is not None:
                metrics['rank'] = manga['rank']
            if manga.get('popularity') is not None:
                metrics['popularity'] = manga['popularity']

            if metrics:
                save_external_metrics_batch(title, 'mal', metrics)
                return True
            return False

    async def _search(self, session: aiohttp.ClientSession, query: str) -> list:
        url = f'{JIKAN_BASE}/manga'
        params = {'q': query, 'limit': 10, 'order_by': 'score', 'sort': 'desc'}
        async with session.get(url, params=params) as resp:
            if resp.status == 429:
                self.logger.warning("Jikan rate limit, 5초 대기...")
                await asyncio.sleep(5)
                return []
            if resp.status != 200:
                return []
            data = await resp.json()
            return data.get('data', [])

    async def _fetch_by_id(self, session: aiohttp.ClientSession, mal_id: int) -> Optional[dict]:
        url = f'{JIKAN_BASE}/manga/{mal_id}'
        async with session.get(url) as resp:
            if resp.status == 429:
                await asyncio.sleep(5)
                return None
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get('data')
