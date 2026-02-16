"""
메챠코믹 (めちゃコミック) 크롤러

특징:
- CSR 방식 (Playwright 필수, Next.js + Tailwind CSS)
- 페이지네이션 3페이지 (각 20개, 총 60개 중 상위 50개)
- URL 기반 페이지네이션: ?page=N
- IP 제한 없음 (한국에서도 접근 가능)

DOM 구조 (2026년 Tailwind CSS 리뉴얼 버전):
<ul class="grid grid-cols-1 lg:grid-cols-2">
  <li class="px-2 ...">
    <div class="flex gap-2.5 ...">
      <div>  <!-- 이미지 영역 -->
        <a href="/books/{id}"><img alt="제목" ...></a>
      </div>
      <div class="flex flex-1 flex-col justify-between">  <!-- 정보 영역 -->
        <span class="align-middle text-[16px] font-bold">1位</span>
        <a href="/books/{id}" class="font-bold text-link ...">제목</a>
        <div class="text-[12px] ...">작가명</div>
        <span class="inline-flex items-center ...">장르태그</span>
      </div>
    </div>
  </li>
</ul>
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser, Page


async def crawl(browser: Browser) -> List[Dict[str, Any]]:
    """
    메챠코믹 판매 랭킹 50위 크롤링

    Args:
        browser: Playwright 브라우저 인스턴스

    Returns:
        [{'rank': 1, 'title': '제목', 'genre': '장르', 'url': 'http://...'}, ...]
    """
    page = await browser.new_page()
    rankings = []

    try:
        # 3페이지 순회 (각 페이지 20개 작품)
        for page_num in range(1, 4):
            if page_num == 1:
                url = 'https://mechacomic.jp/sales_rankings/current'
            else:
                url = f'https://mechacomic.jp/sales_rankings/current?page={page_num}'

            print(f"    페이지 {page_num} 접속 중...")

            await page.goto(url, wait_until='domcontentloaded', timeout=30000)

            # JavaScript 렌더링 대기: 랭킹 그리드가 나타날 때까지
            try:
                await page.wait_for_selector(
                    'ul.grid.grid-cols-1 > li',
                    timeout=15000
                )
            except Exception:
                # Selector 대기 실패 시 추가 대기
                await page.wait_for_timeout(3000)

            # 추가 렌더링 안정화 대기
            await page.wait_for_timeout(1500)

            # 작품 요소 추출: ul.grid.grid-cols-1 > li
            items = await page.query_selector_all('ul.grid.grid-cols-1 > li')
            print(f"    페이지 {page_num}: {len(items)}개 요소 발견")

            for item in items:
                try:
                    parsed = await _parse_ranking_item(item)
                    if parsed:
                        rankings.append(parsed)
                except Exception as e:
                    print(f"    개별 작품 파싱 실패: {e}")
                    continue

        # 중복 제거 및 순위 정렬
        seen = set()
        unique_rankings = []
        for item in rankings:
            if item['rank'] not in seen:
                seen.add(item['rank'])
                unique_rankings.append(item)

        unique_rankings.sort(key=lambda x: x['rank'])

        # 상위 50개만
        result = unique_rankings[:50]

        print(f"    메챠코믹: {len(result)}개 작품 추출")
        return result

    except Exception as e:
        print(f"    메챠코믹 크롤링 실패: {e}")
        raise

    finally:
        await page.close()


async def _parse_ranking_item(item) -> Dict[str, Any]:
    """
    개별 랭킹 아이템 파싱

    Args:
        item: Playwright ElementHandle (li 요소)

    Returns:
        {'rank': N, 'title': '...', 'genre': '...', 'url': '...', 'thumbnail': '...'} or None
    """
    # 1. 순위 추출: <span class="align-middle text-[16px] font-bold">N位</span>
    rank = None
    rank_spans = await item.query_selector_all('span')
    for span in rank_spans:
        text = (await span.inner_text()).strip()
        match = re.match(r'^(\d+)位$', text)
        if match:
            rank = int(match.group(1))
            break

    if rank is None:
        return None

    # 2. 제목 추출: <a class="font-bold text-link ...">제목</a>
    title = ""
    title_links = await item.query_selector_all('a.font-bold')
    for link in title_links:
        cls = await link.get_attribute('class') or ''
        if 'text-link' in cls:
            title = (await link.inner_text()).strip()
            break

    if not title:
        # fallback: 이미지 alt 속성에서 제목 추출
        imgs = await item.query_selector_all('img[alt]')
        for img in imgs:
            alt = await img.get_attribute('alt')
            # 아이콘 이미지 제외 (짧은 키워드들)
            if alt and len(alt) > 3 and alt not in [
                'オリジナル', '独占先行', '続話', '毎日無料プラス',
                '評価', 'NEW'
            ]:
                title = alt.strip()
                break

    if not title:
        return None

    # 3. URL 추출: <a href="/books/{id}">
    full_url = ""
    book_link = await item.query_selector('a[href*="/books/"]')
    if book_link:
        url_path = await book_link.get_attribute('href')
        if url_path:
            if url_path.startswith('http'):
                full_url = url_path
            else:
                full_url = f"https://mechacomic.jp{url_path}"

    # 4. 장르 추출: <span class="inline-flex items-center ...">장르태그</span>
    genres = []
    genre_spans = await item.query_selector_all('span.inline-flex')
    for gs in genre_spans:
        genre_text = (await gs.inner_text()).strip()
        if genre_text:
            genres.append(genre_text)

    # 첫 번째 장르를 메인 장르로 사용
    genre = genres[0] if genres else ""

    # 5. 썸네일 추출: <img class="h-auto max-w-full ...">
    thumbnail = ""
    cover_img = await item.query_selector('img.h-auto')
    if cover_img:
        thumbnail = await cover_img.get_attribute('src') or ""

    return {
        'rank': rank,
        'title': title,
        'genre': genre,
        'url': full_url,
        'thumbnail': thumbnail
    }


if __name__ == "__main__":
    # 테스트 코드
    import asyncio
    from playwright.async_api import async_playwright

    async def test():
        print("=" * 60)
        print("메챠코믹 크롤러 테스트")
        print("=" * 60)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            try:
                result = await crawl(browser)
                print(f"\n총 {len(result)}개 작품 수집")

                if result:
                    print(f"\n샘플 (1~5위):")
                    for item in result[:5]:
                        print(f"  {item['rank']}위: {item['title']}")
                        print(f"    장르: {item['genre']}")
                        print(f"    URL: {item['url']}")
            finally:
                await browser.close()

        print("\n" + "=" * 60)

    asyncio.run(test())
