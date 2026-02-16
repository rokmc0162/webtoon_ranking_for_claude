"""
픽코마 (ピッコマ) 크롤러

특징:
- SSR 방식 (HTML에 모든 데이터 포함, 가장 쉬움)
- SMARTOON 종합 랭킹 크롤링
- 일본 IP 필수
"""

from typing import List, Dict, Any
from playwright.async_api import Browser, Page


async def crawl(browser: Browser) -> List[Dict[str, Any]]:
    """
    픽코마 SMARTOON 종합 랭킹 50위 크롤링

    Args:
        browser: Playwright 브라우저 인스턴스

    Returns:
        [{'rank': 1, 'title': '제목', 'genre': '장르', 'url': 'http://...'}, ...]
    """
    page = await browser.new_page()
    rankings = []

    try:
        # SMARTOON 종합 랭킹 페이지
        url = 'https://piccoma.com/web/ranking/S/P/0'
        print(f"    픽코마 SMARTOON 접속 중...")

        await page.goto(url, wait_until='domcontentloaded', timeout=30000)

        # SSR이므로 즉시 데이터 있음, 하지만 안전하게 대기
        await page.wait_for_selector('.PCM-productList_item, .ranking-item, article', timeout=10000)

        # 작품 요소 추출
        items = await page.query_selector_all('.PCM-productList_item, .ranking-item, article, li')

        print(f"    작품 요소 {len(items)}개 발견")

        for i, item in enumerate(items[:50], 1):  # 상위 50개만
            try:
                # 순위 추출
                rank_elem = await item.query_selector('.rank, .ranking-number, .number')
                rank = i  # 기본값: 순서대로

                if rank_elem:
                    rank_text = await rank_elem.inner_text()
                    try:
                        rank = int(rank_text.strip().replace('位', '').replace('#', ''))
                    except ValueError:
                        rank = i

                # 제목 추출
                title_elem = await item.query_selector('.PCM-product-title, .title, h3, h2')
                title = ""

                if title_elem:
                    title = await title_elem.inner_text()
                else:
                    # 링크의 aria-label이나 title 속성에서 추출
                    link_elem = await item.query_selector('a')
                    if link_elem:
                        title = await link_elem.get_attribute('aria-label')
                        if not title:
                            title = await link_elem.get_attribute('title')

                if not title:
                    # 전체 텍스트에서 추출
                    text = await item.inner_text()
                    lines = [l.strip() for l in text.split('\n') if l.strip()]
                    for line in lines:
                        if len(line) > 3 and '位' not in line and '#' not in line:
                            title = line
                            break

                # URL 추출
                link_elem = await item.query_selector('a')
                url_path = await link_elem.get_attribute('href') if link_elem else ""
                full_url = ""

                if url_path:
                    if url_path.startswith('http'):
                        full_url = url_path
                    else:
                        full_url = f"https://piccoma.com{url_path}"

                # 장르 추출
                genre_elem = await item.query_selector('.genre, .category, .tag')
                genre = ""

                if genre_elem:
                    genre = await genre_elem.inner_text()
                else:
                    # 텍스트에서 장르 키워드 매칭
                    text = await item.inner_text()
                    genre = extract_genre_from_text(text)

                # 썸네일
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

        # 순위 정렬
        rankings.sort(key=lambda x: x['rank'])

        print(f"    ✅ 픽코마: {len(rankings)}개 작품 추출")
        return rankings[:50]  # 상위 50개만

    except Exception as e:
        print(f"    ❌ 픽코마 크롤링 실패: {e}")

        # IP 제한 체크
        page_content = await page.content()
        if '403' in page_content or 'Forbidden' in page_content:
            print(f"    💡 일본 IP가 필요합니다. VPN을 사용하거나 일본 서버에서 실행하세요.")

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
    # 픽코마 장르 (11개)
    genres = [
        'ファンタジー',  # 판타지
        '恋愛',          # 연애
        'アクション',    # 액션
        'ドラマ',        # 드라마
        'ホラー・ミステリー',  # 호러/미스터리
        'ホラー',        # 호러
        'ミステリー',    # 미스터리
        '裏社会・アングラ',    # 뒷세계/언더그라운드
        'スポーツ',      # 스포츠
        'グルメ',        # 요리
        '日常',          # 일상
        'TL',
        'BL'
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
        print("픽코마 크롤러 테스트")
        print("=" * 60)
        print("⚠️  주의: 일본 IP가 필요합니다!")
        print()

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
