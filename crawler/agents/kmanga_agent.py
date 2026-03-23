"""
まんが王国 (K-Manga) 크롤러 에이전트

특징:
- SSR 방식 (HTML에 100개 완전 로드)
- 셀렉터: .book-list li
- 장르: 8개 (종합, 여성, 소녀, 청년, 소년, TL, BL, 오토나)
- 제목: a[href*="/title/"] 링크 텍스트, 썸네일: img[src*="cover_200"]
"""

from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class KmangaAgent(CrawlerAgent):
    """まんが王国 (K-Manga) 종합 + 장르별 랭킹 크롤러"""

    GENRE_RANKINGS = {
        '': {'name': '총합', 'path': '/rank/'},
        '女性漫画': {'name': '여성', 'path': '/rank/female'},
        '少女漫画': {'name': '소녀', 'path': '/rank/girl'},
        '青年漫画': {'name': '청년', 'path': '/rank/male'},
        '少年漫画': {'name': '소년', 'path': '/rank/boy'},
        'TL': {'name': 'TL', 'path': '/rank/tl'},
        'BL': {'name': 'BL', 'path': '/rank/bl'},
        'オトナ': {'name': '오토나', 'path': '/rank/otona'},
    }

    BASE_URL = 'https://comic.k-manga.jp'

    def __init__(self):
        super().__init__(
            platform_id='kmanga',
            platform_name='まんが王国 (K-Manga)',
            url='https://comic.k-manga.jp/rank/'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """まんが王国 종합 + 장르별 랭킹 크롤링"""
        page = await browser.new_page()

        try:
            for genre_key, genre_info in self.GENRE_RANKINGS.items():
                label = genre_info['name']
                url = f"{self.BASE_URL}{genre_info['path']}"

                self.logger.info(f"   📖 [{label}] 크롤링: {url}")

                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                    await page.wait_for_timeout(2000)

                    items = await page.query_selector_all('.book-list li')
                    rankings = []

                    for idx, item in enumerate(items[:100]):
                        try:
                            entry = await self._parse_item(item, idx + 1, genre_key)
                            if entry:
                                rankings.append(entry)
                        except Exception:
                            continue

                    self.logger.info(f"   ✅ [{label}]: {len(rankings)}개 작품")
                    self.genre_results[genre_key] = rankings

                except Exception as e:
                    self.logger.warning(f"   ⚠️ [{label}] 실패: {e}")
                    self.genre_results[genre_key] = []

        finally:
            await page.close()

        # 종합 랭킹 반환
        return self.genre_results.get('', [])

    async def _parse_item(self, item, fallback_rank: int, genre_key: str) -> Dict[str, Any]:
        """개별 랭킹 아이템 파싱"""

        # 1. 순위: .book-list--rank 내 텍스트 (예: "1位")
        rank = fallback_rank
        rank_el = await item.query_selector('.book-list--rank span')
        if rank_el:
            rank_text = (await rank_el.inner_text()).strip()
            try:
                rank = int(rank_text.replace('位', ''))
            except ValueError:
                pass

        # 2. 제목 + URL: a[href*="/title/"]
        title = None
        url = ''
        link_el = await item.query_selector('a[href*="/title/"]')
        if link_el:
            href = await link_el.get_attribute('href') or ''
            url = href if href.startswith('http') else f"{self.BASE_URL}{href}"

            # 이미지의 alt 속성에서 제목 추출 (가장 깨끗한 소스)
            img_el = await link_el.query_selector('img')
            if img_el:
                title = await img_el.get_attribute('alt')

        # 제목 폴백: 링크 텍스트에서 추출
        if not title and link_el:
            full_text = (await link_el.inner_text()).strip()
            # 첫 줄이 제목 (개행 이전)
            lines = [l.strip() for l in full_text.split('\n') if l.strip()]
            # 장르 텍스트 제거
            for line in lines:
                if line and len(line) > 2 and not any(kw in line for kw in
                    ['無料', '割引', '試し読み', 'NEW', '位', '漫画', 'ファンタジー',
                     '恋愛', 'SF', 'アクション', 'ドラマ', 'ホラー', 'ミステリー',
                     'スポーツ', 'グルメ', '日常', 'BL', 'TL', 'オトナ']):
                    title = line
                    break

        if not title:
            return None

        # 3. 썸네일: img[src*="cover"]
        thumbnail_url = ''
        if link_el:
            thumb_el = await link_el.query_selector('img[src*="cover"]')
            if thumb_el:
                thumbnail_url = await thumb_el.get_attribute('src') or ''

        # 4. 장르
        genre = genre_key  # 장르별 페이지에서는 장르가 확정됨

        return {
            'rank': rank,
            'title': title.strip(),
            'genre': genre,
            'url': url,
            'thumbnail_url': thumbnail_url,
        }

    async def save(self, date: str, data: List[Dict[str, Any]]):
        """종합 + 장르별 랭킹 모두 저장"""
        from crawler.db import save_rankings, backup_to_json, save_works_metadata

        # 종합 랭킹 저장
        save_rankings(date, self.platform_id, data, sub_category='')
        works_meta = [
            {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
             'url': item.get('url', ''), 'genre': item.get('genre', ''), 'rank': item.get('rank')}
            for item in data if item.get('thumbnail_url')
        ]
        if works_meta:
            save_works_metadata(self.platform_id, works_meta, date=date, sub_category='')
        backup_to_json(date, self.platform_id, data)

        # 장르별 랭킹 저장
        for genre_key, rankings in self.genre_results.items():
            if genre_key == '' or not rankings:
                continue
            save_rankings(date, self.platform_id, rankings, sub_category=genre_key)
            genre_meta = [
                {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
                 'url': item.get('url', ''), 'genre': item.get('genre', ''), 'rank': item.get('rank')}
                for item in rankings if item.get('thumbnail_url')
            ]
            if genre_meta:
                save_works_metadata(self.platform_id, genre_meta, date=date, sub_category=genre_key)
