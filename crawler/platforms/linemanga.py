"""
라인망가 (LINE マンガ) 크롤러

특징:
- CSR 방식 (JavaScript 렌더링 필수!)
- 무한 스크롤 처리 필요
- 일본 IP 필수
- 웹 종합 랭킹만 크롤링 (앱과 상이)

⚠️ 주의: 일반 HTTP 요청으로는 빈 HTML만 받아옴. 반드시 Playwright 사용!
"""

from typing import List, Dict, Any
from playwright.async_api import Browser, Page


async def crawl(browser: Browser) -> List[Dict[str, Any]]:
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
        # 웹 종합 랭킹 (gender=0)
        url = 'https://manga.line.me/periodic/gender_ranking?gender=0'
        print(f"    라인망가 웹 종합 랭킹 접속 중...")

        await page.goto(url, wait_until='networkidle', timeout=30000)

        # JavaScript 렌더링 대기 (중요!)
        # 라인망가는 a[hint] 셀렉터 사용 (hint 속성에 제목)
        try:
            await page.wait_for_selector('a[hint], .ranking-item, article', timeout=15000)
        except Exception:
            # IP 제한 체크
            page_content = await page.content()
            if '日本国内でのみ利用可能' in page_content or '403' in page_content:
                print(f"    ❌ 일본 IP가 필요합니다. 현재 위치에서는 접근 불가능합니다.")
                raise Exception("IP 제한: 일본 IP 필요")
            raise

        # 무한 스크롤로 50개 작품 로드
        print(f"    무한 스크롤 처리 중...")
        for scroll_count in range(15):  # 15번 스크롤 (충분히 50개 이상)
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(500)  # 로딩 대기

            # 현재 로드된 작품 수 확인
            current_items = await page.query_selector_all('a[hint]')
            if len(current_items) >= 50:
                print(f"    50개 이상 로드 완료 (현재 {len(current_items)}개)")
                break

        # 작품 요소 추출
        items = await page.query_selector_all('a[hint]')
        print(f"    작품 요소 {len(items)}개 발견")

        for i, item in enumerate(items[:50], 1):  # 상위 50개만
            try:
                # 순위
                rank = i

                # 제목 (hint 속성에 있음)
                title = await item.get_attribute('hint')

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
                genre = extract_genre_from_text(text)

                # 썸네일
                img_elem = await item.query_selector('img')
                thumbnail = ""

                if img_elem:
                    # data-src 우선, 없으면 src
                    thumbnail = await img_elem.get_attribute('data-src')
                    if not thumbnail:
                        thumbnail = await img_elem.get_attribute('src')

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

        print(f"    ✅ 라인망가: {len(rankings)}개 작품 추출")
        return rankings

    except Exception as e:
        print(f"    ❌ 라인망가 크롤링 실패: {e}")

        # IP 제한 체크
        try:
            page_content = await page.content()
            if '日本国内でのみ利用可能' in page_content:
                print(f"    💡 라인망가는 일본 국내에서만 이용 가능합니다.")
                print(f"    💡 일본 VPN을 사용하거나 일본 서버에서 실행하세요.")
        except:
            pass

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
        'ファンタジー',  # 판타지
        '恋愛',          # 연애
        'アクション',    # 액션
        'ドラマ',        # 드라마
        'ホラー',        # 호러
        'ミステリー',    # 미스터리
        'コメディ',      # 코미디
        'サスペンス',    # 서스펜스
        'SF',
        '学園',          # 학원
        'スポーツ',      # 스포츠
        'グルメ',        # 요리
        '日常',          # 일상
        'BL',
        'TL',
        '異世界',        # 이세계
        '転生',          # 전생
        '復讐',          # 복수
        'バトル'         # 배틀
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
        print("라인망가 크롤러 테스트")
        print("=" * 60)
        print("⚠️  주의: 일본 IP가 필요합니다!")
        print("⚠️  CSR이므로 JavaScript 렌더링 필수!")
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
