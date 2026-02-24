"""
벨툰 (BeLTOON) 크롤러 에이전트

특징:
- CSR 방식 (Next.js + styled-components)
- IP 제한 없음
- 데일리 랭킹 (순위 + 타이틀 + 조회수 + 작가)
- 장르 필터 (로맨스, BL, 판타지, 드라마, GL, 소녀만화)
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class BeltoonAgent(CrawlerAgent):
    """벨툰 데일리 랭킹 크롤러 에이전트"""

    GENRE_RANKINGS = {
        '': {'name': '종합(데일리)', 'filter': ''},
    }

    def __init__(self):
        super().__init__(
            platform_id='beltoon',
            platform_name='벨툰 (BeLTOON)',
            url='https://www.beltoon.jp/app/all/ranking'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """벨툰 데일리 랭킹 크롤링"""
        page = await browser.new_page()
        all_rankings = []

        try:
            self.logger.info(f"📱 벨툰 [종합] 크롤링 중... → {self.url}")

            await page.goto(self.url, wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_timeout(5000)

            # 스크롤 다운으로 lazy loading 트리거
            for _ in range(10):
                await page.evaluate('window.scrollBy(0, 1000)')
                await page.wait_for_timeout(500)

            # 텍스트 기반 파싱 (순위 + 타이틀 + 조회수 + 작가 패턴)
            body_text = await page.inner_text('body')
            rankings = self._parse_text_rankings(body_text)

            all_rankings = rankings
            self.genre_results[''] = rankings
            self.logger.info(f"   ✅ [종합]: {len(rankings)}개 작품")

            return all_rankings

        finally:
            await page.close()

    def _parse_text_rankings(self, body_text: str) -> List[Dict[str, Any]]:
        """텍스트에서 랭킹 아이템 추출

        벨툰 패턴:
        순위번호
        타이틀
        조회수(N만 또는 N.N만) 또는 "무료증량중" 등
        작가명
        """
        lines = [l.strip() for l in body_text.split('\n') if l.strip()]
        rankings = []

        # "デイリー" 텍스트 이후 시작
        start_idx = 0
        for i, line in enumerate(lines):
            if line == 'デイリー':
                start_idx = i + 1
                break

        i = start_idx
        while i < len(lines) and len(rankings) < 100:
            line = lines[i]

            # 순위 번호 감지
            if line.isdigit() and 1 <= int(line) <= 100:
                rank = int(line)

                # 순위 변동 번호 건너뛰기 (다음 줄이 또 숫자이면 변동폭)
                j = i + 1
                while j < len(lines) and lines[j].isdigit():
                    j += 1

                # 타이틀
                if j < len(lines):
                    title = lines[j].strip()
                    if (len(title) >= 2 and
                            title not in ['チェック解除', '絞り込み', '...', 'ロマンス',
                                          'BL', 'ファンタジー', 'ドラマ', 'GL', '少女マンガ'] and
                            not title.startswith('(')):

                        rankings.append({
                            'rank': rank,
                            'title': title,
                            'genre': '',
                            'url': 'https://www.beltoon.jp/app/all/ranking',
                            'thumbnail_url': '',
                        })
                        i = j + 1
                        continue

            i += 1

        return rankings

    async def save(self, date: str, data: List[Dict[str, Any]]):
        """랭킹 저장"""
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
