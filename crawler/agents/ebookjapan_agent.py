"""
이북재팬 (ebookjapan / Yahoo) 크롤러 에이전트

특징:
- SSR+CSR 하이브리드 (Vue.js)
- IP 제한 없음
- 카테고리 탭별 랭킹 (총합, 소녀/여성, 소년/청년, 판타지, BL, TL 등)
- 초기 10개만 표시, "もっと見る" 클릭으로 확장
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class EbookjapanAgent(CrawlerAgent):
    """이북재팬 일간 랭킹 크롤러 에이전트"""

    GENRE_RANKINGS = {
        '': {'name': '종합', 'path': '/ranking/'},
        '少女・女性': {'name': '소녀/여성', 'path': '/ranking/category/1/'},
        '少年・青年': {'name': '소년/청년', 'path': '/ranking/category/2/'},
        'ファンタジー': {'name': '판타지', 'path': '/ranking/category/26/'},
        'BL': {'name': 'BL', 'path': '/ranking/category/5/'},
        'TL': {'name': 'TL', 'path': '/ranking/category/4/'},
    }

    def __init__(self):
        super().__init__(
            platform_id='ebookjapan',
            platform_name='이북재팬 (ebookjapan)',
            url='https://ebookjapan.yahoo.co.jp/ranking/'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """이북재팬 종합 + 카테고리별 랭킹 크롤링"""
        page = await browser.new_page()
        all_rankings = []

        try:
            for genre_key, genre_info in self.GENRE_RANKINGS.items():
                label = genre_info['name']
                path = genre_info['path']
                url = f'https://ebookjapan.yahoo.co.jp{path}'

                self.logger.info(f"📱 이북재팬 [{label}] 크롤링 중... → {url}")

                await page.goto(url, wait_until='domcontentloaded', timeout=20000)
                await page.wait_for_timeout(4000)

                # "もっと見る" 버튼 클릭 시도 (더 많은 아이템 로드)
                try:
                    more_btn = await page.query_selector('a:has-text("もっと見る")')
                    if more_btn:
                        await more_btn.click()
                        await page.wait_for_timeout(3000)
                except Exception:
                    pass

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
        """텍스트에서 랭킹 아이템 추출"""
        lines = [l.strip() for l in body_text.split('\n') if l.strip()]
        rankings = []

        # ebookjapan은 "총합ランキング" 이후 타이틀 + (권수) + 장르 패턴
        # 타이틀 행 뒤에 (N) 형태의 권수, 그 뒤에 장르 표기
        in_ranking = False
        rank = 0

        for i, line in enumerate(lines):
            if 'ランキング' in line and ('総合' in line or '少女' in line or
                                        '少年' in line or 'ファンタジー' in line):
                in_ranking = True
                continue

            if not in_ranking:
                continue

            # "もっと見る" 이후 새 섹션
            if line == 'もっと見る':
                continue

            # 장르 태그 (스킵)
            if line in ['少女マンガ', '女性マンガ', '青年マンガ', '少年マンガ',
                         'BLコミック', 'TLコミック', 'ラノベ']:
                continue

            # 권수 표기 (스킵)
            if re.match(r'^（\d+）$', line):
                continue

            # 짧은 유틸리티 텍스트 스킵
            if len(line) < 3 or line in ['有料', '無料', '前日', '週間', '月間',
                                          '歴代', 'トップ', '総合']:
                continue

            # 타이틀 후보
            if len(line) >= 3 and not line.startswith('http'):
                rank += 1
                if rank <= 100:
                    # 다음 줄에서 장르 추출 시도
                    genre = genre_key
                    if i + 2 < len(lines):
                        next_next = lines[i + 2].strip() if i + 2 < len(lines) else ''
                        if next_next in ['少女マンガ', '女性マンガ', '青年マンガ',
                                         '少年マンガ']:
                            genre = next_next

                    rankings.append({
                        'rank': rank,
                        'title': line,
                        'genre': genre,
                        'url': 'https://ebookjapan.yahoo.co.jp/ranking/',
                        'thumbnail_url': '',
                    })

        return rankings[:100]

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
            self.logger.info(f"   💾 [{genre_name}]: {len(rankings)}개 저장")
