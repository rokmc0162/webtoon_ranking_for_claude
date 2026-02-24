"""
AniList GraphQL API 수집기.
- 무료, API 키 불필요
- POST https://graphql.anilist.co
- 만화 검색 → 점수(0-100), 인기도, 팬 수, 상태
"""
import aiohttp
from typing import Optional

from crawler.sns.base_collector import BaseCollector
from crawler.sns.external_db import (
    get_cached_external_id, save_external_id, save_external_metrics_batch
)
from crawler.sns.title_matcher import best_match

ANILIST_URL = 'https://graphql.anilist.co'

SEARCH_QUERY = '''
query ($search: String) {
  Page(page: 1, perPage: 10) {
    media(search: $search, type: MANGA, sort: SEARCH_MATCH) {
      id
      title { romaji english native }
      averageScore
      popularity
      favourites
      status
      genres
      format
    }
  }
}
'''

FETCH_BY_ID_QUERY = '''
query ($id: Int) {
  Media(id: $id, type: MANGA) {
    id
    title { romaji english native }
    averageScore
    popularity
    favourites
    status
    genres
    format
  }
}
'''


class AnilistCollector(BaseCollector):

    def __init__(self):
        super().__init__(source_name='anilist', rate_limit_delay=1.0)

    async def collect_one(self, title: str, platform: str) -> bool:
        cached_id = get_cached_external_id(title, 'anilist')

        async with aiohttp.ClientSession() as session:
            media = None
            match_score = 1.0

            if cached_id:
                media = await self._fetch_by_id(session, int(cached_id))
            else:
                candidates = await self._search(session, title)
                if not candidates:
                    return False

                result = best_match(
                    title,
                    [self._flatten_titles(c) for c in candidates],
                    threshold=0.75
                )
                if not result:
                    return False

                media, match_score = result
                save_external_id(
                    platform=platform, title=title, source='anilist',
                    external_id=str(media['id']),
                    external_title=media.get('native', '') or media.get('romaji', ''),
                    match_score=match_score
                )

            if not media:
                return False

            metrics = {}
            if media.get('averageScore') is not None:
                metrics['score'] = media['averageScore']
            if media.get('popularity') is not None:
                metrics['popularity'] = media['popularity']
            if media.get('favourites') is not None:
                metrics['members'] = media['favourites']
            if media.get('status'):
                metrics['status'] = media['status']

            if metrics:
                save_external_metrics_batch(title, 'anilist', metrics)
                return True
            return False

    async def _search(self, session: aiohttp.ClientSession, query: str) -> list:
        payload = {'query': SEARCH_QUERY, 'variables': {'search': query}}
        async with session.post(ANILIST_URL, json=payload) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            return data.get('data', {}).get('Page', {}).get('media', [])

    async def _fetch_by_id(self, session: aiohttp.ClientSession, media_id: int) -> Optional[dict]:
        payload = {'query': FETCH_BY_ID_QUERY, 'variables': {'id': media_id}}
        async with session.post(ANILIST_URL, json=payload) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get('data', {}).get('Media')

    def _flatten_titles(self, media: dict) -> dict:
        """AniList의 title 객체를 top-level 키로 펼침 (매칭용)."""
        flat = dict(media)
        title_obj = media.get('title', {})
        flat['native'] = title_obj.get('native', '')
        flat['romaji'] = title_obj.get('romaji', '')
        flat['english'] = title_obj.get('english', '')
        return flat
