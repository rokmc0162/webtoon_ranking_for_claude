"""
U-NEXT 무료만화 크롤러 에이전트

특징:
- CSR (JavaScript 렌더링 필요)
- 카테고리 랭킹: /book/categoryranking/D_C_COMIC?genre=freecomic
- a[href*="/book/title/"] 로 아이템 추출
- 제목은 inner_text에서 파싱 (毎日無料, New, X話無料, 순위 제거)
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class UnextFreeAgent(CrawlerAgent):
    """U-NEXT 무료만화 랭킹 크롤러"""

    BASE_URL = 'https://video.unext.jp'

    def __init__(self):
        super().__init__(
            platform_id='unext',
            platform_name='U-NEXT (무료만화)',
            url='https://video.unext.jp/book/genre/freecomic'
        )
        self.genre_results = {}
        self._sub_category = '無料マンガ'  # unext 플랫폼 내 하위 카테고리

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """U-NEXT 무료만화 랭킹 크롤링"""
        page = await browser.new_page()

        try:
            # 메인 무료만화 페이지에서 랭킹 섹션 수집
            url = f"{self.BASE_URL}/book/genre/freecomic"
            self.logger.info(f"   📖 [무료만화] 크롤링: {url}")

            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(8000)  # CSR 렌더링 대기

            rankings = await self._parse_rankings(page)
            self.logger.info(f"   ✅ [무료만화]: {len(rankings)}개 작품")

            # 더 적으면 카테고리 랭킹 페이지도 시도
            if len(rankings) < 15:
                self.logger.info("   📖 카테고리 랭킹 페이지 시도...")
                rank_url = f"{self.BASE_URL}/book/categoryranking/D_C_COMIC?genre=freecomic"
                await page.goto(rank_url, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_timeout(8000)

                alt_rankings = await self._parse_rankings(page)
                if len(alt_rankings) > len(rankings):
                    rankings = alt_rankings
                    self.logger.info(f"   ✅ [카테고리 랭킹]: {len(rankings)}개 작품")

            self.genre_results[''] = rankings

        finally:
            await page.close()

        return rankings

    async def _parse_rankings(self, page) -> List[Dict[str, Any]]:
        """페이지에서 랭킹 아이템 파싱"""
        links = await page.query_selector_all('a[href*="/book/title/"]')
        rankings = []
        seen_ids = set()

        for link in links:
            try:
                href = await link.get_attribute('href') or ''
                m = re.search(r'/book/title/([A-Z0-9]+)', href)
                if not m:
                    continue
                book_id = m.group(1)
                if book_id in seen_ids:
                    continue

                # inner_text에서 제목과 순위 추출
                full_text = (await link.inner_text()).strip()
                if not full_text:
                    continue

                # 배너/프로모션 링크 스킵 (날짜 패턴으로 시작하는 것)
                if re.match(r'^\d{8}', full_text):
                    continue

                # 제목 파싱: "毎日無料\nNew\n제목\n\nX話無料\n\n순위" 패턴
                lines = [l.strip() for l in full_text.split('\n') if l.strip()]

                title = None
                rank = None

                # 순위 추출 (마지막 숫자)
                for line in reversed(lines):
                    try:
                        rank = int(line)
                        break
                    except ValueError:
                        continue

                if rank is None:
                    continue  # 순위가 없으면 랭킹 아이템이 아님

                # 제목 추출 (毎日無料, New, X話無料, 숫자를 제외한 의미있는 텍스트)
                skip_patterns = ['毎日無料', 'New', '無料', '配信開始', '話無料', '冊無料']
                for line in lines:
                    if any(p in line for p in skip_patterns):
                        continue
                    try:
                        int(line)
                        continue  # 숫자만 있는 줄 스킵
                    except ValueError:
                        pass
                    if len(line) >= 2:
                        title = line
                        break

                if not title:
                    continue

                seen_ids.add(book_id)

                # 썸네일
                thumbnail_url = ''
                img = await link.query_selector('img')
                if img:
                    thumbnail_url = await img.get_attribute('src') or ''

                url = f"{self.BASE_URL}{href}" if not href.startswith('http') else href

                rankings.append({
                    'rank': rank,
                    'title': title.strip(),
                    'genre': '',
                    'url': url,
                    'thumbnail_url': thumbnail_url,
                })

            except Exception:
                continue

        # 순위순 정렬
        rankings.sort(key=lambda x: x['rank'])
        return rankings

    async def save(self, date: str, data: List[Dict[str, Any]]):
        """unext 플랫폼의 無料マンガ 하위 카테고리로 저장"""
        from crawler.db import save_rankings, backup_to_json, save_works_metadata

        save_rankings(date, self.platform_id, data, sub_category=self._sub_category)
        works_meta = [
            {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
             'url': item.get('url', ''), 'genre': item.get('genre', ''), 'rank': item.get('rank')}
            for item in data if item.get('thumbnail_url')
        ]
        if works_meta:
            save_works_metadata(self.platform_id, works_meta, date=date, sub_category=self._sub_category)
        backup_to_json(date, 'unext_free', data)  # 백업은 별도 파일명
