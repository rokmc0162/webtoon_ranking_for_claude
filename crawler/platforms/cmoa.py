"""
코믹시모아 (コミックシーモア) 크롤러

특징:
- CSR + TLS 이슈 (fetch 시 에러, Playwright 필수)
- 단일 페이지 (50개 작품)
- IP 제한 없음
"""

from typing import List, Dict, Any
from playwright.async_api import Browser, Page


async def crawl(browser: Browser) -> List[Dict[str, Any]]:
    """
    코믹시모아 종합 랭킹 50위 크롤링

    Args:
        browser: Playwright 브라우저 인스턴스

    Returns:
        [{'rank': 1, 'title': '제목', 'genre': '장르', 'url': 'http://...'}, ...]
    """
    # TLS 에러 우회를 위해 ignore_https_errors 설정
    context = await browser.new_context(ignore_https_errors=True)
    page = await context.new_page()
    rankings = []

    try:
        url = 'https://www.cmoa.jp/search/purpose/ranking/all/'
        print(f"    코믹시모아 접속 중...")

        await page.goto(url, wait_until='networkidle', timeout=30000)

        # JavaScript 렌더링 대기
        await page.wait_for_selector('li.search_result_box, .ranking-item, article', timeout=10000)

        # 작품 요소 추출
        # 주의: 실제 셀렉터는 페이지 구조에 따라 조정 필요
        items = await page.query_selector_all('li.search_result_box, .ranking-item, .rank-item, article')

        print(f"    작품 요소 {len(items)}개 발견")

        for i, item in enumerate(items[:50], 1):  # 상위 50개만
            try:
                # 순위는 보통 순서대로 나열됨
                rank = i

                # 제목 추출
                title_elem = await item.query_selector('.title, .work-title, h3, h2, a')
                title = ""

                if title_elem:
                    title = await title_elem.inner_text()
                else:
                    # 전체 텍스트에서 추출
                    text = await item.inner_text()
                    lines = text.split('\n')
                    for line in lines:
                        if len(line) > 3:
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
                        full_url = f"https://www.cmoa.jp{url_path}"

                # 장르 추출
                genre_elem = await item.query_selector('.genre, .category')
                genre = ""

                if genre_elem:
                    genre = await genre_elem.inner_text()
                else:
                    # 텍스트에서 장르 키워드 매칭
                    text = await item.inner_text()
                    genre = extract_genre_from_text(text)

                # 썸네일 (선택사항)
                img_elem = await item.query_selector('img')
                thumbnail = ""

                if img_elem:
                    thumbnail = await img_elem.get_attribute('src')
                    if not thumbnail:
                        thumbnail = await img_elem.get_attribute('data-src')

                if title:  # 제목이 있는 경우만 추가
                    rankings.append({
                        'rank': rank,
                        'title': title.strip(),
                        'genre': genre.strip() if genre else "",
                        'url': full_url,
                        'thumbnail': thumbnail
                    })

            except Exception as e:
                print(f"    ⚠️  {i}번째 작품 파싱 실패: {e}")
                continue

        print(f"    ✅ 코믹시모아: {len(rankings)}개 작품 추출")
        return rankings

    except Exception as e:
        print(f"    ❌ 코믹시모아 크롤링 실패: {e}")
        raise

    finally:
        await page.close()
        await context.close()


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
        print("코믹시모아 크롤러 테스트")
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
