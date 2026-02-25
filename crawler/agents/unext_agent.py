"""
U-NEXT 크롤러 에이전트

특징:
- CSR 방식 (Next.js + Apollo GraphQL)
- IP 제한 없음
- styled-components → picture > img 구조, metac.nxtv.jp 도메인
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
        """U-NEXT 만화 랭킹 크롤링 - GraphQL route intercept로 5페이지 수집"""
        import json
        import urllib.parse

        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()

        try:
            self.logger.info(f"📱 U-NEXT [만화] 크롤링 중... → {self.url}")

            all_books = []
            current_page_target = [1]  # mutable for closure

            # GraphQL 응답 캡처
            async def on_response(response):
                if 'cosmo_getBookRanking' in response.url:
                    try:
                        body = await response.json()
                        books = body.get('data', {}).get('bookRanking', {}).get('books', [])
                        for book in books:
                            s = book.get('bookSakuhin', {})
                            if not s or not s.get('name'):
                                continue
                            # 썸네일: book.thumbnail.standard
                            thumb = s.get('book', {}).get('thumbnail', {}).get('standard', '')
                            if thumb and not thumb.startswith('http'):
                                thumb = 'https://' + thumb
                            all_books.append({
                                'name': s.get('name', ''),
                                'code': s.get('sakuhinCode', ''),
                                'thumb': thumb,
                            })
                    except Exception:
                        pass

            page.on('response', on_response)

            # Route intercept: page 파라미터를 현재 타겟으로 변경
            async def modify_request(route):
                url = route.request.url
                if 'cosmo_getBookRanking' in url and current_page_target[0] > 1:
                    parsed = urllib.parse.urlparse(url)
                    params = urllib.parse.parse_qs(parsed.query)
                    if 'variables' in params:
                        variables = json.loads(params['variables'][0])
                        variables['page'] = current_page_target[0]
                        params['variables'] = [json.dumps(variables)]
                        new_query = urllib.parse.urlencode({k: v[0] for k, v in params.items()})
                        new_url = f'{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}'
                        await route.continue_(url=new_url)
                        return
                await route.continue_()

            await page.route('**/cc.unext.jp/**', modify_request)

            # 페이지 1: 일반 로드
            await page.goto(self.url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(8000)
            self.logger.info(f"   Page 1: {len(all_books)}개 수집")

            # 페이지 2-5: 페이지 재로드 + route intercept
            for pg in range(2, 6):
                current_page_target[0] = pg
                await page.goto(self.url, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_timeout(5000)
                self.logger.info(f"   Page {pg}: {len(all_books)}개 누적")

            # 중복 제거 및 랭킹 구성
            seen = set()
            rankings = []
            for book in all_books:
                if book['name'] and book['name'] not in seen:
                    seen.add(book['name'])
                    rankings.append({
                        'rank': len(rankings) + 1,
                        'title': book['name'],
                        'genre': '',
                        'url': f"https://video.unext.jp/book/title/{book['code']}" if book['code'] else '',
                        'thumbnail_url': book.get('thumb', ''),
                    })
                    if len(rankings) >= 100:
                        break

            # route 해제
            await page.unroute('**/cc.unext.jp/**')

            # 폴백: GraphQL 실패 시 DOM 방식
            if len(rankings) < 5:
                self.logger.info(f"   GraphQL 부족({len(rankings)}개), DOM 폴백...")
                for _ in range(15):
                    await page.evaluate('window.scrollBy(0, 800)')
                    await page.wait_for_timeout(500)
                rankings = await self._parse_dom_rankings(page)

            self.genre_results[''] = rankings
            self.logger.info(f"   ✅ [만화]: {len(rankings)}개 작품")

            return rankings

        finally:
            await page.close()

    async def _parse_dom_rankings(self, page) -> List[Dict[str, Any]]:
        """DOM에서 랭킹 아이템 + 썸네일 추출"""
        items = await page.evaluate("""() => {
            const results = [];
            // U-NEXT: picture > img 구조, metac.nxtv.jp 도메인
            // 랭킹 아이템은 a 태그로 감싸짐
            const allLinks = document.querySelectorAll('a[href*="/book/title/"]');
            const seen = new Set();
            let rank = 0;

            for (const a of allLinks) {
                const img = a.querySelector('picture img, img');
                if (!img) continue;

                const src = img.getAttribute('src') || '';
                if (!src || src.includes('logo') || src.includes('icon')) continue;

                // U-NEXT 이미지 도메인
                if (!src.includes('nxtv.jp') && !src.includes('unext')) continue;

                const alt = img.getAttribute('alt') || '';
                let title = alt;
                if (!title || title.length < 2) {
                    // 링크 내 텍스트에서 추출
                    const textEls = a.querySelectorAll('span, p, h3');
                    for (const el of textEls) {
                        const t = el.textContent.trim();
                        if (t.length >= 2 && t.length <= 100 && !/^\\d+$/.test(t) &&
                            !t.includes('無料') && !t.includes('New')) {
                            title = t;
                            break;
                        }
                    }
                }
                if (!title || title.length < 2) continue;

                // 중복 방지
                if (seen.has(title)) continue;
                seen.add(title);

                const href = a.getAttribute('href') || '';
                const fullUrl = href.startsWith('http') ? href : 'https://video.unext.jp' + href;

                rank++;
                if (rank <= 100) {
                    results.push({
                        rank: rank,
                        title: title,
                        url: fullUrl,
                        thumbnail_url: src,
                    });
                }
            }
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

    def _parse_text_rankings(self, body_text: str) -> List[Dict[str, Any]]:
        """텍스트에서 랭킹 아이템 추출 - 폴백"""
        lines = [l.strip() for l in body_text.split('\n') if l.strip()]
        rankings = []

        start_idx = 0
        for i, line in enumerate(lines):
            if line == 'ランキング' and i > 10:
                start_idx = i + 1
                break

        i = start_idx
        while i < len(lines):
            if lines[i].isdigit() and 1 <= int(lines[i]) <= 100:
                break
            i += 1

        while i < len(lines) and len(rankings) < 100:
            line = lines[i]

            if line.isdigit() and 1 <= int(line) <= 100:
                rank = int(line)
                j = i + 1
                while j < len(lines):
                    candidate = lines[j].strip()
                    if candidate in ['New', ''] or re.match(r'^\d+冊無料$', candidate):
                        j += 1
                        continue
                    break

                if j < len(lines):
                    title = lines[j].strip()
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
            for item in data if item.get('thumbnail_url')
        ]
        if works_meta:
            save_works_metadata(self.platform_id, works_meta, date=date, sub_category='')
        backup_to_json(date, self.platform_id, data)
