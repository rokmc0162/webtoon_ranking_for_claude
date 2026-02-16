"""
라인망가 (LINE マンガ) 크롤러 에이전트

특징:
- CSR 방식 (JavaScript 렌더링 필수!)
- 무한 스크롤 처리 필요
- 일본 IP 필수
- 웹 종합 랭킹만 크롤링 (앱과 상이)

⚠️ 주의: 일반 HTTP 요청으로는 빈 HTML만 받아옴. 반드시 Playwright 사용!
"""

from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent
from crawler.utils import get_korean_title, is_riverse_title, translate_genre


class LinemangaAgent(CrawlerAgent):
    """라인망가 웹 종합 랭킹 크롤러 에이전트"""

    def __init__(self):
        super().__init__(
            platform_id='linemanga',
            platform_name='라인망가 (웹 종합)',
            url='https://manga.line.me/periodic/gender_ranking?gender=0'
        )

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """
        라인망가 웹 종합 랭킹 50위 크롤링

        Args:
            browser: Playwright 브라우저 인스턴스

        Returns:
            [{'rank': 1, 'title': '제목', 'genre': '장르', 'url': 'http://...'}, ...]
        """
        page = await browser.new_page()
        rankings = []

        try:
            self.logger.info(f"📱 {self.platform_name} 크롤링 중...")
            self.logger.info(f"   URL: {self.url}")

            # networkidle이 필요 (CSR 방식)
            await page.goto(self.url, wait_until='networkidle', timeout=30000)

            # JavaScript 렌더링 대기 (중요!)
            # 라인망가는 a[hint] 셀렉터 사용 (hint 속성에 제목)
            try:
                await page.wait_for_selector('a[hint], .ranking-item, article', timeout=15000)
            except Exception:
                # IP 제한 체크
                page_content = await page.content()
                if '日本国内でのみ利用可能' in page_content or '403' in page_content:
                    self.logger.error("❌ 일본 IP가 필요합니다. 현재 위치에서는 접근 불가능합니다.")
                    raise Exception("IP 제한: 일본 IP 필요")
                raise

            # 무한 스크롤로 50개 작품 로드
            self.logger.debug("무한 스크롤 처리 중...")
            for scroll_count in range(15):  # 15번 스크롤 (충분히 50개 이상)
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(500)  # 로딩 대기

                # 현재 로드된 작품 수 확인
                current_items = await page.query_selector_all('a[hint]')
                if len(current_items) >= 50:
                    self.logger.debug(f"50개 이상 로드 완료 (현재 {len(current_items)}개)")
                    break

            # 작품 요소 추출
            items = await page.query_selector_all('a[hint]')
            self.logger.info(f"   작품 요소 {len(items)}개 발견")

            for i, item in enumerate(items[:50], 1):  # 상위 50개만
                try:
                    # 순위
                    rank = i

                    # 제목 (hint 속성에 있음)
                    title = await item.get_attribute('hint')

                    if not title:
                        continue

                    # URL
                    url_path = await item.get_attribute('href')
                    full_url = ""

                    if url_path:
                        if url_path.startswith('http'):
                            full_url = url_path
                        else:
                            full_url = f"https://manga.line.me{url_path}"

                    # 장르 (텍스트에서 추출)
                    text = await item.inner_text()
                    genre = self._extract_genre_from_text(text)

                    # 한국어 제목 및 리버스 여부 확인
                    title_kr = get_korean_title(title)
                    is_riverse = is_riverse_title(title)
                    genre_kr = translate_genre(genre)

                    rankings.append({
                        'rank': rank,
                        'title': title.strip(),
                        'title_kr': title_kr,
                        'genre': genre.strip() if genre else "",
                        'genre_kr': genre_kr,
                        'url': full_url,
                        'is_riverse': is_riverse
                    })

                except Exception as e:
                    self.logger.debug(f"{i}번째 작품 파싱 실패: {e}")
                    continue

            self.logger.info(f"   ✅ {self.platform_name}: {len(rankings)}개 작품 수집 완료")
            return rankings

        finally:
            await page.close()

    def _extract_genre_from_text(self, text: str) -> str:
        """텍스트에서 장르 키워드 추출"""
        genres = [
            'ファンタジー', '恋愛', 'アクション', 'ドラマ', 'ホラー', 'ミステリー',
            'コメディ', 'サスペンス', 'SF', '学園', 'スポーツ', 'グルメ',
            '日常', 'BL', 'TL', '異世界', '転生', '復讐', 'バトル', '歴史'
        ]

        for genre in genres:
            if genre in text:
                return genre

        return ""


if __name__ == "__main__":
    # 테스트 코드
    import asyncio
    from playwright.async_api import async_playwright

    async def test():
        print("=" * 60)
        print("라인망가 에이전트 테스트")
        print("=" * 60)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)

            try:
                agent = LinemangaAgent()
                result = await agent.execute(browser)

                print(f"\n✅ Success: {result.success}")
                print(f"✅ Count: {result.count}")

                if result.success and result.data:
                    print(f"\n샘플 (1~3위):")
                    for item in result.data[:3]:
                        print(f"  {item['rank']}위: {item['title']}")
                        if item['title_kr']:
                            print(f"    한국어: {item['title_kr']}")
                        print(f"    장르: {item['genre']} ({item['genre_kr']})")
                        print(f"    리버스: {item['is_riverse']}")
                else:
                    print(f"\n❌ Error: {result.error}")

            finally:
                await browser.close()

        print("\n" + "=" * 60)

    asyncio.run(test())
