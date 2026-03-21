"""
라인망가 (LINE マンガ) 크롤러 에이전트

특징:
- SSR+CSR 하이브리드 (domcontentloaded로 충분)
- 일본 IP 필수
- 90개 작품이 한 페이지에 로드됨 (스크롤 불필요)
- 종합: /periodic/gender_ranking?gender=0 (ol > li, MdCMN14Num 순위 있음)
- 장르별: /genre_list?genre_id=XXXX (순위 번호 없음, 위치 기반)
"""

from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class LinemangaAgent(CrawlerAgent):
    """라인망가 웹 종합 + 장르별 랭킹 크롤러 에이전트"""

    # 장르별 랭킹 URL 매핑 (/genre_list?genre_id=XXXX)
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
        'その他': {'name': '기타', 'genre_id': 'ffff'},
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

        종합 DOM 구조 (/periodic/gender_ranking):
        <div class="MdCMN05List">
          <ol>
            <li>
              <a href="/product/periodic?id=..." title="제목">
                <span class="MdCMN14Num">1</span>
                <div class="MdCMN06Img"><img alt="제목" src="..."></div>
                <span class="mdCMN05Ttl">제목</span>
                <ul class="mdCMN05InfoList">
                  <li>ファンタジー・SF</li>
                </ul>
              </a>
            </li>
          </ol>
        </div>

        장르별 DOM 구조 (/genre_list?genre_id=XXXX):
        <div class="MdCMN05List">
          <li>
            <a href="/product/periodic?id=..." title="제목">
              <div class="MdCMN06Img"><img alt="제목" src="..."></div>
              <span class="mdCMN05Ttl">제목</span>
            </a>
          </li>
        </div>
        (순위 번호 없음 - 위치 기반으로 순위 결정)
        """
        page = await browser.new_page()
        all_rankings = []

        try:
            # ===== 1. 종합 랭킹 (/periodic/gender_ranking) =====
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
            # 90개만 로드된 경우 스크롤로 추가 로드
            if len(items) < 100:
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(2000)
                items = await page.query_selector_all('.MdCMN05List ol > li')
            self.logger.info(f"   작품 요소 {len(items)}개 발견")

            for item in items[:100]:
                try:
                    entry = await self._parse_item(item)
                    if entry:
                        all_rankings.append(entry)
                except Exception as e:
                    self.logger.debug(f"작품 파싱 실패: {e}")
                    continue

            self.logger.info(f"   ✅ [총합]: {len(all_rankings)}개 작품")
            self.genre_results[''] = all_rankings

            # ===== 2. 장르별 랭킹 (/genre_list?genre_id=XXXX 페이지 직접 크롤링) =====
            for genre_key, genre_info in self.GENRE_RANKINGS.items():
                if genre_key == '':
                    continue

                genre_id = genre_info['genre_id']
                label = genre_info['name']
                self.logger.info(f"📱 라인망가 [{label}] 크롤링 중...")

                try:
                    rankings = await self._crawl_genre_page(page, genre_id, genre_key)
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

    async def _crawl_genre_page(self, page, genre_id: str, genre_key: str) -> List[Dict[str, Any]]:
        """장르별 랭킹 페이지 직접 크롤링 (/genre_list?genre_id=XXXX)"""
        url = f"https://manga.line.me/genre_list?genre_id={genre_id}"

        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_selector('a[href*="/product/"]', timeout=15000)
        await page.wait_for_timeout(2000)

        # 장르 페이지에서 product 링크를 가진 아이템 추출
        # .MdCMN05List 내의 a[href*="/product/"] 요소들
        product_links = await page.query_selector_all('.MdCMN05List a[href*="/product/"]')
        # 90개만 로드된 경우 스크롤로 추가 로드
        if len(product_links) < 100:
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(2000)
            product_links = await page.query_selector_all('.MdCMN05List a[href*="/product/"]')
        self.logger.info(f"   상품 링크 {len(product_links)}개 발견")

        rankings = []
        seen_titles = set()
        rank = 0

        for link in product_links:
            try:
                # 제목: title 속성
                title = await link.get_attribute('title')
                if not title:
                    img = await link.query_selector('img')
                    if img:
                        title = await img.get_attribute('alt') or ''
                if not title or title in seen_titles:
                    continue

                seen_titles.add(title)
                rank += 1

                # URL
                href = await link.get_attribute('href') or ''
                item_url = f"https://manga.line.me{href}" if href and not href.startswith('http') else href

                # 썸네일
                thumbnail_url = ''
                thumb_img = await link.query_selector('.MdCMN06Img img')
                if thumb_img:
                    thumbnail_url = await thumb_img.get_attribute('src') or ''

                rankings.append({
                    'rank': rank,
                    'title': title.strip(),
                    'genre': genre_key,
                    'url': item_url,
                    'thumbnail_url': thumbnail_url,
                })

                if rank >= 100:
                    break

            except Exception as e:
                self.logger.debug(f"장르 아이템 파싱 실패: {e}")
                continue

        return rankings

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
            if genre_key == '':
                continue
            genre_name = self.GENRE_RANKINGS[genre_key]['name']
            save_rankings(date, self.platform_id, rankings, sub_category=genre_key)
            genre_meta = [
                {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
                 'url': item.get('url', ''), 'genre': item.get('genre', ''), 'rank': item.get('rank')}
                for item in rankings if item.get('thumbnail_url')
            ]
            if genre_meta:
                save_works_metadata(self.platform_id, genre_meta, date=date, sub_category=genre_key)
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
