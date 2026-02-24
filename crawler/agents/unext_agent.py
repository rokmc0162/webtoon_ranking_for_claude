"""
U-NEXT 크롤러 에이전트

특징:
- CSR 방식 (Next.js + Apollo GraphQL)
- IP 제한 없음
- 텍스트에서 순위 추출 (숫자 + 타이틀 패턴)
- 만화 랭킹 (/book/ranking/comic)
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class UnextAgent(CrawlerAgent):
    """U-NEXT 만화 랭킹 크롤러 에이전트"""

    def __init__(self):
        super().__init__(
            platform_id='unext',
            platform_name='U-NEXT (만화)',
            url='https://video.unext.jp/book/ranking/comic'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """U-NEXT 만화 랭킹 크롤링"""
        page = await browser.new_page()

        try:
            self.logger.info(f"📱 U-NEXT [만화] 크롤링 중... → {self.url}")

            await page.goto(self.url, wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_timeout(5000)

            # 스크롤 다운으로 lazy loading 트리거 (더 많은 아이템)
            for _ in range(15):
                await page.evaluate('window.scrollBy(0, 800)')
                await page.wait_for_timeout(500)

            # 텍스트 기반 파싱
            body_text = await page.inner_text('body')
            rankings = self._parse_text_rankings(body_text)

            self.genre_results[''] = rankings
            self.logger.info(f"   ✅ [만화]: {len(rankings)}개 작품")

            return rankings

        finally:
            await page.close()

    def _parse_text_rankings(self, body_text: str) -> List[Dict[str, Any]]:
        """텍스트에서 랭킹 아이템 추출

        U-NEXT 패턴:
        순위번호
        타이틀 (권수 포함)
        부가정보(무료, New 등)
        """
        lines = [l.strip() for l in body_text.split('\n') if l.strip()]
        rankings = []

        # "ランキング" 이후 시작
        start_idx = 0
        for i, line in enumerate(lines):
            if line == 'ランキング' and i > 10:  # 네비게이션이 아닌 본문의 ランキング
                start_idx = i + 1
                break

        # 첫 번째 추천 작품 건너뛰기 (광고/프로모션)
        i = start_idx
        # 첫 번째 숫자(순위)를 찾을 때까지 건너뛰기
        while i < len(lines):
            if lines[i].isdigit() and 1 <= int(lines[i]) <= 100:
                break
            i += 1

        while i < len(lines) and len(rankings) < 100:
            line = lines[i]

            if line.isdigit() and 1 <= int(line) <= 100:
                rank = int(line)
                # 다음 줄(들)에서 타이틀 찾기
                j = i + 1
                # "New", "N冊無料" 등 건너뛰기
                while j < len(lines):
                    candidate = lines[j].strip()
                    if candidate in ['New', ''] or re.match(r'^\d+冊無料$', candidate):
                        j += 1
                        continue
                    break

                if j < len(lines):
                    title = lines[j].strip()
                    # 유효한 타이틀인지 확인
                    if (len(title) >= 2 and
                            not re.match(r'^\d+$', title) and
                            title not in ['マンガ', 'ラノベ', '書籍', 'ホーム']):
                        rankings.append({
                            'rank': rank,
                            'title': title,
                            'genre': '',
                            'url': 'https://video.unext.jp/book/ranking/comic',
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
