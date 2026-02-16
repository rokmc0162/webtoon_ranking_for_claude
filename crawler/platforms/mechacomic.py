"""
메챠코믹 (めちゃコミック) 크롤러

특징:
- CSR 방식 (Playwright 필수)
- 페이지네이션 3페이지 (약 50개 작품)
- IP 제한 없음 (한국에서도 테스트 가능)
"""

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
        # 3페이지 순회 (각 페이지 약 17개 작품)
        for page_num in range(1, 4):
            url = f'https://mechacomic.jp/sales_rankings/current?page={page_num}'
            print(f"    페이지 {page_num} 접속 중...")

            await page.goto(url, wait_until='networkidle', timeout=30000)

            # JavaScript 렌더링 대기
            await page.wait_for_selector('.ranking-item, .rank-item, article', timeout=10000)

            # 작품 요소 추출
            # 주의: 실제 셀렉터는 페이지 구조에 따라 조정 필요
            items = await page.query_selector_all('.ranking-item, .rank-item, article')

            for item in items:
                try:
                    # 순위 추출 ("N位" 텍스트 찾기)
                    rank_text = await item.inner_text()
                    rank = None

                    # "N位" 패턴 찾기
                    if '位' in rank_text:
                        for line in rank_text.split('\n'):
                            if '位' in line:
                                try:
                                    rank = int(line.replace('位', '').strip())
                                    break
                                except ValueError:
                                    continue

                    if not rank:
                        continue  # 순위 없으면 스킵

                    # 제목 추출
                    title_elem = await item.query_selector('.title, .work-title, h3, h2')
                    title = await title_elem.inner_text() if title_elem else ""

                    if not title:
                        # 텍스트에서 제목 추출 (첫 번째 긴 줄)
                        lines = rank_text.split('\n')
                        for line in lines:
                            if len(line) > 3 and '位' not in line:
                                title = line.strip()
                                break

                    # URL 추출
                    link_elem = await item.query_selector('a')
                    url_path = await link_elem.get_attribute('href') if link_elem else ""
                    full_url = ""
                    if url_path:
                        if url_path.startswith('http'):
                            full_url = url_path
                        else:
                            full_url = f"https://mechacomic.jp{url_path}"

                    # 장르 추출 (텍스트에서 키워드 매칭)
                    genre = extract_genre_from_text(rank_text)

                    # 썸네일 (선택사항)
                    img_elem = await item.query_selector('img')
                    thumbnail = await img_elem.get_attribute('src') if img_elem else ""

                    rankings.append({
                        'rank': rank,
                        'title': title.strip(),
                        'genre': genre,
                        'url': full_url,
                        'thumbnail': thumbnail
                    })

                except Exception as e:
                    print(f"    ⚠️  개별 작품 파싱 실패: {e}")
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

        print(f"    ✅ 메챠코믹: {len(result)}개 작품 추출")
        return result

    except Exception as e:
        print(f"    ❌ 메챠코믹 크롤링 실패: {e}")
        raise

    finally:
        await page.close()


def extract_genre_from_text(text: str) -> str:
    """
    텍스트에서 장르 키워드 추출

    Args:
        text: 작품 정보 텍스트

    Returns:
        장르 (없으면 빈 문자열)
    """
    # 일본어 장르 키워드
    genres = [
        'ファンタジー', '恋愛', 'アクション', 'ドラマ', 'ホラー', 'ミステリー',
        'コメディ', 'サスペンス', 'SF', '学園', 'スポーツ', 'グルメ',
        '日常', 'BL', 'TL', '異世界', '転生', '復讐', 'バトル'
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
        print("메챠코믹 크롤러 테스트")
        print("=" * 60)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)  # 디버깅용

            try:
                result = await crawl(browser)
                print(f"\n✅ 총 {len(result)}개 작품 수집")

                if result:
                    print(f"\n샘플 (1~3위):")
                    for item in result[:3]:
                        print(f"  {item['rank']}위: {item['title']}")
                        print(f"    장르: {item['genre']}")
                        print(f"    URL: {item['url']}")
            finally:
                await browser.close()

        print("\n" + "=" * 60)

    asyncio.run(test())
