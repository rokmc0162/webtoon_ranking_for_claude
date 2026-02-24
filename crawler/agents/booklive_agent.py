"""
북라이브 (BookLive) 크롤러 에이전트

특징:
- SSR 방식 (서버 렌더링, 가장 데이터 풍부)
- 100개/페이지, 페이지네이션 있음
- IP 제한 없음
- 순위번호, 타이틀, 작가, 장르, 가격 등 풍부한 메타데이터
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class BookliveAgent(CrawlerAgent):
    """북라이브 일간/종합 랭킹 크롤러 에이전트"""

    GENRE_RANKINGS = {
        '': {'name': '종합', 'path': '/ranking/day'},
        '少年マンガ': {'name': '소년만화', 'path': '/ranking/day/10001'},
        '青年マンガ': {'name': '청년만화', 'path': '/ranking/day/10003'},
        '少女マンガ': {'name': '소녀만화', 'path': '/ranking/day/10002'},
        '女性マンガ': {'name': '여성만화', 'path': '/ranking/day/10004'},
        'BL': {'name': 'BL', 'path': '/ranking/day/10005'},
        'TL': {'name': 'TL', 'path': '/ranking/day/10006'},
        'ラノベ': {'name': '라노벨', 'path': '/ranking/day/10009'},
    }

    def __init__(self):
        super().__init__(
            platform_id='booklive',
            platform_name='북라이브 (BookLive)',
            url='https://booklive.jp/ranking/day'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """북라이브 종합 + 장르별 랭킹 크롤링"""
        page = await browser.new_page()
        all_rankings = []

        try:
            for genre_key, genre_info in self.GENRE_RANKINGS.items():
                label = genre_info['name']
                path = genre_info['path']
                url = f'https://booklive.jp{path}'

                self.logger.info(f"📱 북라이브 [{label}] 크롤링 중... → {url}")

                await page.goto(url, wait_until='domcontentloaded', timeout=20000)
                await page.wait_for_timeout(3000)

                # 텍스트 기반 파싱
                body_text = await page.inner_text('body')
                rankings = self._parse_text_rankings(body_text, genre_key)

                self.genre_results[genre_key] = rankings
                self.logger.info(f"   ✅ [{label}]: {len(rankings)}개 작품")

                if genre_key == '':
                    all_rankings = rankings

            return all_rankings

        finally:
            await page.close()

    def _parse_text_rankings(self, body_text: str, genre_key: str) -> List[Dict[str, Any]]:
        """텍스트에서 랭킹 아이템 추출 (N位 패턴)"""
        lines = [l.strip() for l in body_text.split('\n') if l.strip()]
        rankings = []

        i = 0
        while i < len(lines) and len(rankings) < 100:
            line = lines[i]
            # "N位" 패턴 감지
            rank_match = re.match(r'^(\d+)位$', line)
            if rank_match:
                rank = int(rank_match.group(1))
                # 다음 줄 = 타이틀
                if i + 1 < len(lines):
                    title = lines[i + 1].strip()
                    if len(title) >= 2 and not title.endswith('位'):
                        # 장르 찾기 (타이틀 이후 줄들에서)
                        genre = genre_key
                        if not genre:
                            for j in range(i + 2, min(i + 6, len(lines))):
                                g = lines[j].strip()
                                if g in ['少年マンガ', '青年マンガ', '少女マンガ',
                                         '女性マンガ', 'BL', 'TL', 'ラノベ']:
                                    genre = g
                                    break

                        rankings.append({
                            'rank': rank,
                            'title': title,
                            'genre': genre,
                            'url': 'https://booklive.jp/ranking/day',
                            'thumbnail_url': '',
                        })
            i += 1

        return rankings

    async def save(self, date: str, data: List[Dict[str, Any]]):
        """종합 + 장르별 랭킹 모두 저장"""
        from crawler.db import save_rankings, backup_to_json, save_works_metadata

        save_rankings(date, self.platform_id, data, sub_category='')
        works_meta = [
            {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
             'url': item.get('url', ''), 'genre': item.get('genre', ''), 'rank': item.get('rank')}
            for item in data if item.get('title')
        ]
        if works_meta:
            save_works_metadata(self.platform_id, works_meta, date=date, sub_category='')
        backup_to_json(date, self.platform_id, data)

        for genre_key, rankings in self.genre_results.items():
            if genre_key == '':
                continue
            genre_name = self.GENRE_RANKINGS[genre_key]['name']
            save_rankings(date, self.platform_id, rankings, sub_category=genre_key)
            genre_meta = [
                {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
                 'url': item.get('url', ''), 'genre': item.get('genre', ''), 'rank': item.get('rank')}
                for item in rankings if item.get('title')
            ]
            if genre_meta:
                save_works_metadata(self.platform_id, genre_meta, date=date, sub_category=genre_key)
            self.logger.info(f"   💾 [{genre_name}]: {len(rankings)}개 저장")
