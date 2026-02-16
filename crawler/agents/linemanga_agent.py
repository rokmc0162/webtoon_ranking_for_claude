"""
라인망가 (LINE マンガ) 크롤러 에이전트

특징:
- SSR+CSR 하이브리드 (domcontentloaded로 충분)
- 일본 IP 필수
- 90개 작품이 한 페이지에 로드됨 (스크롤 불필요)
- 셀렉터: .MdCMN05List ol > li (2026년 현재 구조)
- 장르별 랭킹: JSON API (/api/ranking/product_genre_weekly_ranking) 활용
"""

import json
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class LinemangaAgent(CrawlerAgent):
    """라인망가 웹 종합 + 장르별 랭킹 크롤러 에이전트"""

    # 장르별 랭킹 URL 매핑 (product_genre_weekly_ranking API)
    GENRE_RANKINGS = {
        '': {'name': '총합'},
        'バトル・アクション': {'name': '배틀/액션', 'genre_id': '0001'},
        'ファンタジー・SF': {'name': '판타지/SF', 'genre_id': '0002'},
        '恋愛': {'name': '연애', 'genre_id': '0003'},
        'スポーツ': {'name': '스포츠', 'genre_id': '0004'},
        'ミステリー・ホラー': {'name': '미스터리/호러', 'genre_id': '0005'},
        '裏社会・アングラ': {'name': '뒷세계/언더', 'genre_id': '0006'},
        'ヒューマンドラマ': {'name': '휴먼드라마', 'genre_id': '0007'},
        '歴史・時代': {'name': '역사/시대', 'genre_id': '0008'},
        'コメディ・ギャグ': {'name': '코미디/개그', 'genre_id': '0009'},
        'BL': {'name': 'BL', 'genre_id': '0010'},
        'TL': {'name': 'TL', 'genre_id': '0011'},
        'その他': {'name': '기타', 'genre_id': '0013'},
    }

    def __init__(self):
        super().__init__(
            platform_id='linemanga',
            platform_name='라인망가 (웹 종합)',
            url='https://manga.line.me/periodic/gender_ranking?gender=0'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """
        라인망가 웹 종합 + 장르별 랭킹 크롤링

        DOM 구조 (종합):
        <div class="MdCMN05List">
          <ol>
            <li>
              <a href="/product/periodic?id=..." title="제목">
                <span class="MdCMN14Num">1</span>
                <div class="MdCMN06Img"><img alt="제목" src="..."></div>
                <span class="mdCMN05Ttl">제목</span>
                <ul class="mdCMN05InfoList">
                  <li>ファンタジー・SF</li>
                  <li>毎週金曜更新</li>
                </ul>
              </a>
            </li>
          </ol>
        </div>
        """
        page = await browser.new_page()
        all_rankings = []

        try:
            # ===== 1. 종합 랭킹 (기존 방식: periodic/gender_ranking) =====
            self.logger.info(f"📱 라인망가 [총합] 크롤링 중...")
            self.logger.info(f"   URL: {self.url}")

            await page.goto(self.url, wait_until='domcontentloaded', timeout=30000)

            try:
                await page.wait_for_selector('.MdCMN05List ol > li', timeout=15000)
            except Exception:
                content = await page.content()
                if '日本国内' in content or len(content) < 1000:
                    self.logger.error("❌ 일본 IP가 필요합니다.")
                    raise Exception("IP 제한: 일본 IP 필요")
                raise

            await page.wait_for_timeout(2000)

            items = await page.query_selector_all('.MdCMN05List ol > li')
            self.logger.info(f"   작품 요소 {len(items)}개 발견")

            for item in items[:50]:
                try:
                    entry = await self._parse_item(item)
                    if entry:
                        all_rankings.append(entry)
                except Exception as e:
                    self.logger.debug(f"작품 파싱 실패: {e}")
                    continue

            self.logger.info(f"   ✅ [총합]: {len(all_rankings)}개 작품")
            self.genre_results[''] = all_rankings

            # ===== 2. 장르별 랭킹 (JSON API: product_genre_weekly_ranking) =====
            for genre_key, genre_info in self.GENRE_RANKINGS.items():
                if genre_key == '':
                    continue

                genre_id = genre_info['genre_id']
                label = genre_info['name']
                self.logger.info(f"📱 라인망가 [{label}] 크롤링 중...")

                try:
                    rankings = await self._crawl_genre_api(page, genre_id, genre_key)
                    self.genre_results[genre_key] = rankings
                    self.logger.info(f"   ✅ [{label}]: {len(rankings)}개 작품")
                except Exception as e:
                    self.logger.warning(f"   ⚠️ [{label}] 실패: {e}")
                    self.genre_results[genre_key] = []

            return all_rankings

        finally:
            await page.close()

    async def _parse_item(self, item) -> Dict[str, Any]:
        """개별 랭킹 아이템 파싱"""

        # 링크 요소
        link = await item.query_selector('a[href*="/product/"]')
        if not link:
            return None

        # 1. 순위: <span class="MdCMN14Num">N</span>
        rank_el = await item.query_selector('.MdCMN14Num')
        if not rank_el:
            return None
        rank_text = (await rank_el.inner_text()).strip()
        try:
            rank = int(rank_text)
        except ValueError:
            return None

        # 2. 제목: title 속성 또는 <span class="mdCMN05Ttl">
        title = await link.get_attribute('title')
        if not title:
            title_el = await item.query_selector('.mdCMN05Ttl')
            if title_el:
                title = (await title_el.inner_text()).strip()
        if not title:
            return None

        # 3. URL
        href = await link.get_attribute('href') or ''
        url = f"https://manga.line.me{href}" if href and not href.startswith('http') else href

        # 4. 장르: <ul class="mdCMN05InfoList"><li>장르</li>...</ul>
        genre = ''
        genre_el = await item.query_selector('.mdCMN05InfoList li:first-child')
        if genre_el:
            genre = (await genre_el.inner_text()).strip()

        # 5. 썸네일: .MdCMN06Img img src
        thumbnail_url = ''
        thumb_img = await item.query_selector('.MdCMN06Img img')
        if thumb_img:
            thumbnail_url = await thumb_img.get_attribute('src') or ''

        return {
            'rank': rank,
            'title': title.strip(),
            'genre': genre,
            'url': url,
            'thumbnail_url': thumbnail_url,
        }

    async def _crawl_genre_api(self, page, genre_id: str, genre_key: str) -> List[Dict[str, Any]]:
        """JSON API로 장르별 랭킹 수집 (product_genre_weekly_ranking)"""
        api_url = f"https://manga.line.me/api/ranking/product_genre_weekly_ranking?genre_id={genre_id}&page=1&rows=50"

        # 이미 manga.line.me 도메인에 있으므로 fetch 사용 가능
        json_data = await page.evaluate('''
            async (url) => {
                const resp = await fetch(url);
                return await resp.json();
            }
        ''', api_url)

        rankings = []
        rows = json_data.get('result', {}).get('rows', [])
        for i, row in enumerate(rows[:50], 1):
            title = row.get('name', '')
            if not title:
                continue

            product_id = row.get('id', '')
            url = f"https://manga.line.me/book/product_list?product_id={product_id}" if product_id else ''
            thumbnail = row.get('thumbnail', '')

            rankings.append({
                'rank': row.get('rank', i),
                'title': title,
                'genre': genre_key,
                'url': url,
                'thumbnail_url': thumbnail,
            })

        return rankings

    async def save(self, date: str, data: List[Dict[str, Any]]):
        """종합 + 장르별 랭킹 모두 저장"""
        from crawler.db import save_rankings, backup_to_json, save_works_metadata

        # 종합 랭킹 저장 (기존 방식)
        save_rankings(date, self.platform_id, data, sub_category='')
        works_meta = [
            {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
             'url': item.get('url', '')}
            for item in data if item.get('thumbnail_url')
        ]
        if works_meta:
            save_works_metadata(self.platform_id, works_meta)
        backup_to_json(date, self.platform_id, data)

        # 장르별 랭킹 저장
        for genre_key, rankings in self.genre_results.items():
            if genre_key == '':
                continue
            genre_name = self.GENRE_RANKINGS[genre_key]['name']
            save_rankings(date, self.platform_id, rankings, sub_category=genre_key)
            genre_meta = [
                {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
                 'url': item.get('url', '')}
                for item in rankings if item.get('thumbnail_url')
            ]
            if genre_meta:
                save_works_metadata(self.platform_id, genre_meta)
            self.logger.info(f"   💾 [{genre_name}]: {len(rankings)}개 저장")


if __name__ == "__main__":
    import asyncio
    from playwright.async_api import async_playwright

    async def test():
        print("=" * 60)
        print("라인망가 에이전트 테스트")
        print("=" * 60)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            try:
                agent = LinemangaAgent()
                result = await agent.execute(browser)

                print(f"\n✅ Success: {result.success}")
                print(f"✅ Count: {result.count}")

                if result.success and result.data:
                    print(f"\n샘플 (1~5위):")
                    for item in result.data[:5]:
                        print(f"  {item['rank']}위: {item['title']}")
                        print(f"    장르: {item['genre']}")
                        print(f"    URL: {item['url']}")

                    # 장르별 결과 요약
                    print(f"\n장르별 결과:")
                    for gkey, rankings in agent.genre_results.items():
                        label = agent.GENRE_RANKINGS[gkey]['name']
                        print(f"  [{label}]: {len(rankings)}개")
                else:
                    print(f"\n❌ Error: {result.error}")

            finally:
                await browser.close()

        print("\n" + "=" * 60)

    asyncio.run(test())
