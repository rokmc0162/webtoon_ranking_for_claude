"""
렌타 (Renta!) 크롤러 에이전트

특징:
- SSR 방식 (HTML 직접 렌더링)
- IP 제한 없음
- 카테고리별 랭킹 표시 (소녀, 소년, 청년, BL, TL 등)
- 각 카테고리 섹션에서 아이템 추출
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class RentaAgent(CrawlerAgent):
    """렌타 마이너치 랭킹 크롤러 에이전트"""

    GENRE_RANKINGS = {
        '': {'name': '종합', 'path': '/renta/sc/frm/page/ranking_c.htm'},
    }

    def __init__(self):
        super().__init__(
            platform_id='renta',
            platform_name='렌타 (Renta!)',
            url='https://renta.papy.co.jp/renta/sc/frm/page/ranking_c.htm'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """렌타 랭킹 크롤링"""
        ctx = await browser.new_context(
            locale='ja-JP',
            viewport={'width': 1366, 'height': 768},
            ignore_https_errors=True,
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/120.0.0.0 Safari/537.36',
        )
        page = await ctx.new_page()
        all_rankings = []

        try:
            self.logger.info(f"📱 렌타 [종합] 크롤링 중... → {self.url}")

            await page.goto(self.url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(5000)

            # 텍스트 기반으로 모든 카테고리의 랭킹 추출
            body_text = await page.inner_text('body')
            lines = [l.strip() for l in body_text.split('\n') if l.strip()]

            # 카테고리별로 아이템 추출
            # Renta는 카테고리 헤더 + 아이템 목록 구조
            # 아이템은 "試し読み" 패턴을 기준으로 구분
            rankings = []
            rank = 0

            for i, line in enumerate(lines):
                # 타이틀 후보: 충분히 긴 텍스트 (네비게이션 제외)
                if (len(line) >= 4 and
                    line not in ['試し読み', '無料登録', 'ランキング', 'もっと見る'] and
                    not line.startswith('レンタル') and
                    not line.startswith('マンガ') and
                    '配信中' not in line):

                    # 이전 줄이 "試し読み"이면 다음 작품의 시작
                    # 또는 이전 줄이 카테고리 헤더이면
                    if i > 0:
                        prev = lines[i - 1] if i > 0 else ''
                        # 카테고리 헤더 패턴 감지
                        categories = ['少女漫画', '少年漫画', '青年漫画', '映像化作品',
                                      'ボーイズラブ', 'ティーンズラブ', '女性漫画',
                                      'レディース', 'ハーレクイン', 'タテコミ']

                        is_after_category = prev in categories
                        is_after_trial = prev == '試し読み'

                        if is_after_category or (is_after_trial and rank > 0):
                            rank += 1
                            if rank <= 100:
                                rankings.append({
                                    'rank': rank,
                                    'title': line,
                                    'genre': '',
                                    'url': 'https://renta.papy.co.jp',
                                    'thumbnail_url': '',
                                })

            # Fallback: evaluate JS로 링크 기반 추출
            if len(rankings) < 10:
                self.logger.info("   텍스트 파싱 부족, JS evaluate 시도...")
                rankings = await self._extract_via_js(page)

            all_rankings = rankings[:100]
            self.genre_results[''] = all_rankings
            self.logger.info(f"   ✅ [종합]: {len(all_rankings)}개 작품")

            return all_rankings

        finally:
            await page.close()
            await ctx.close()

    async def _extract_via_js(self, page) -> List[Dict[str, Any]]:
        """JavaScript evaluate로 직접 추출"""
        items = await page.evaluate("""() => {
            const results = [];
            // 카테고리 섹션별 추출
            const sections = document.querySelectorAll('ul');
            let rank = 0;

            sections.forEach(ul => {
                const lis = ul.querySelectorAll('li');
                lis.forEach(li => {
                    const a = li.querySelector('a[href*="/frm/item/"]');
                    if (!a) return;

                    const title = a.textContent.trim();
                    if (!title || title.length < 2) return;

                    const href = a.getAttribute('href') || '';
                    const img = li.querySelector('img');
                    const thumbSrc = img ? (img.getAttribute('src') || '') : '';

                    rank++;
                    if (rank <= 100) {
                        results.push({
                            rank: rank,
                            title: title,
                            url: href.startsWith('http') ? href : 'https://renta.papy.co.jp' + href,
                            thumbnail_url: thumbSrc.startsWith('http') ? thumbSrc : (thumbSrc.startsWith('/') ? 'https://renta.papy.co.jp' + thumbSrc : ''),
                        });
                    }
                });
            });

            return results;
        }""")

        return [
            {
                'rank': item['rank'],
                'title': item['title'],
                'genre': '',
                'url': item.get('url', ''),
                'thumbnail_url': item.get('thumbnail_url', ''),
            }
            for item in items[:100]
        ]

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
