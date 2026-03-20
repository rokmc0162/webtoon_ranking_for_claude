"""3개 플랫폼 DOM/네트워크 상세 분석"""
import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from playwright.async_api import async_playwright


async def debug_comico():
    """코미코: 타이틀 파싱 정확도 확인"""
    print("\n" + "=" * 60)
    print("=== 코미코 DOM 분석 ===")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://www.comico.jp/menu/all_comic/ranking', wait_until='domcontentloaded', timeout=20000)
        await page.wait_for_timeout(5000)

        # 첫 번째 li의 전체 구조 분석
        structure = await page.evaluate("""() => {
            const items = document.querySelectorAll('li');
            const results = [];
            let rank = 0;
            for (const li of items) {
                const img = li.querySelector('div.thumbnail img, figure img');
                if (!img) continue;
                const src = img.getAttribute('src') || '';
                if (!src.includes('comico')) continue;
                rank++;
                if (rank > 5) break;

                // li의 전체 innerHTML (처음 500자)
                const html = li.innerHTML.substring(0, 600);
                // li 내의 모든 텍스트 노드들
                const textNodes = [];
                const walker = document.createTreeWalker(li, NodeFilter.SHOW_TEXT);
                while (walker.nextNode()) {
                    const t = walker.currentNode.textContent.trim();
                    if (t.length > 0) textNodes.push(t);
                }

                // 부모 구조
                const a = li.querySelector('a');
                const aHref = a ? a.getAttribute('href') : '';

                // 제목 후보들
                const h2 = li.querySelector('h2');
                const h3 = li.querySelector('h3');
                const captionDiv = li.querySelector('div.caption');
                const titleDiv = li.querySelector('div.title');
                const nameSpan = li.querySelector('[class*="name"], [class*="title"]');

                results.push({
                    rank: rank,
                    imgSrc: src.substring(0, 80),
                    imgAlt: (img.getAttribute('alt') || '').substring(0, 40),
                    aHref: aHref,
                    textNodes: textNodes.slice(0, 10),
                    h2: h2 ? h2.textContent.trim() : null,
                    h3: h3 ? h3.textContent.trim() : null,
                    captionText: captionDiv ? captionDiv.textContent.trim().substring(0, 80) : null,
                    titleDivText: titleDiv ? titleDiv.textContent.trim() : null,
                    nameSpanText: nameSpan ? nameSpan.textContent.trim() : null,
                    liClasses: li.className,
                    html: html,
                });
            }
            return results;
        }""")

        for item in structure:
            print(f"\n--- Rank {item['rank']} ---")
            print(f"  li.class: [{item['liClasses']}]")
            print(f"  a href: [{item['aHref']}]")
            print(f"  img alt: [{item['imgAlt']}]")
            print(f"  h2: [{item['h2']}]")
            print(f"  h3: [{item['h3']}]")
            print(f"  caption: [{item['captionText']}]")
            print(f"  titleDiv: [{item['titleDivText']}]")
            print(f"  nameSpan: [{item['nameSpanText']}]")
            print(f"  textNodes: {item['textNodes']}")
            print(f"  HTML: {item['html'][:300]}")

        await browser.close()


async def debug_lezhin():
    """레진: API 분석 - 네트워크 요청 가로채기"""
    print("\n" + "=" * 60)
    print("=== 레진 네트워크 분석 ===")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        api_calls = []

        async def handle_response(response):
            url = response.url
            if '/api/' in url and 'ranking' in url:
                try:
                    body = await response.json()
                    api_calls.append({'url': url, 'status': response.status, 'body_keys': list(body.keys()) if isinstance(body, dict) else 'array', 'sample': str(body)[:500]})
                except:
                    api_calls.append({'url': url, 'status': response.status, 'body_keys': 'parse_error'})

        page.on('response', handle_response)

        await page.goto('https://lezhin.jp/ranking', wait_until='domcontentloaded', timeout=20000)
        await page.wait_for_timeout(5000)

        # 스크롤 5회
        for _ in range(5):
            await page.evaluate('window.scrollBy(0, 1000)')
            await page.wait_for_timeout(1000)

        print(f"\n캡처된 API 호출: {len(api_calls)}개")
        for i, call in enumerate(api_calls[:10]):
            print(f"\n  [{i+1}] {call['url'][:100]}")
            print(f"      status: {call['status']}")
            print(f"      keys: {call['body_keys']}")
            print(f"      sample: {call.get('sample', '')[:300]}")

        # 직접 API URL 시도
        print("\n--- 직접 API 호출 테스트 ---")
        # genres API
        genres_result = await page.evaluate("""async () => {
            try {
                const resp = await fetch('/api/genres?type=genre_rank');
                if (resp.ok) {
                    const data = await resp.json();
                    return {ok: true, data: data};
                }
                return {ok: false, status: resp.status};
            } catch(e) {
                return {ok: false, error: e.message};
            }
        }""")
        print(f"\n  /api/genres: {json.dumps(genres_result, ensure_ascii=False)[:500]}")

        # ranking API (첫 페이지)
        if genres_result.get('ok') and genres_result.get('data'):
            genres = genres_result['data']
            if isinstance(genres, list) and len(genres) > 0:
                first_genre = genres[0]
                genre_hash = first_genre.get('hash_id', first_genre.get('id', ''))
                print(f"\n  첫 장르: {first_genre.get('name', 'unknown')}, hash: {genre_hash}")

                ranking_result = await page.evaluate("""async (genreHash) => {
                    try {
                        const resp = await fetch('/api/ranking?genre_hash_id=' + genreHash + '&type=daily');
                        if (resp.ok) {
                            const data = await resp.json();
                            const items = data.items || data.data || data;
                            const count = Array.isArray(items) ? items.length : 'not_array';
                            const sample = Array.isArray(items) ? items.slice(0, 2) : data;
                            return {ok: true, count: count, hasMore: !!data.cursor || !!data.next, keys: Object.keys(data), sample: JSON.stringify(sample).substring(0, 500)};
                        }
                        return {ok: false, status: resp.status};
                    } catch(e) {
                        return {ok: false, error: e.message};
                    }
                }""", genre_hash)
                print(f"\n  /api/ranking 결과: {json.dumps(ranking_result, ensure_ascii=False)[:500]}")

        await browser.close()


async def debug_unext():
    """U-NEXT: GraphQL 네트워크 분석"""
    print("\n" + "=" * 60)
    print("=== U-NEXT 네트워크 분석 ===")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        graphql_calls = []

        async def handle_response(response):
            url = response.url
            if 'cc.unext.jp' in url or ('graphql' in url.lower()):
                try:
                    body = await response.json()
                    graphql_calls.append({
                        'url': url[:100],
                        'status': response.status,
                        'sample': json.dumps(body, ensure_ascii=False)[:500]
                    })
                except:
                    graphql_calls.append({'url': url[:100], 'status': response.status, 'sample': 'parse_error'})
            elif 'ranking' in url.lower() or 'book' in url.lower():
                if response.status == 200 and 'json' in (response.headers.get('content-type', '')):
                    try:
                        body = await response.json()
                        graphql_calls.append({
                            'url': url[:100],
                            'status': response.status,
                            'sample': json.dumps(body, ensure_ascii=False)[:300]
                        })
                    except:
                        pass

        page.on('response', handle_response)

        await page.goto('https://video.unext.jp/book/ranking/comic', wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(3000)

        print(f"\n캡처된 API 호출: {len(graphql_calls)}개")
        for i, call in enumerate(graphql_calls[:15]):
            print(f"\n  [{i+1}] {call['url']}")
            print(f"      status: {call['status']}")
            print(f"      sample: {call['sample'][:300]}")

        # 스크롤해서 추가 API 호출 확인
        print("\n--- 스크롤 후 추가 API 호출 ---")
        pre_count = len(graphql_calls)
        for _ in range(3):
            await page.evaluate('window.scrollBy(0, 1000)')
            await page.wait_for_timeout(1500)

        new_calls = graphql_calls[pre_count:]
        print(f"  스크롤 후 추가 호출: {len(new_calls)}개")
        for call in new_calls[:5]:
            print(f"    {call['url']}")
            print(f"    sample: {call['sample'][:300]}")

        await browser.close()


async def main():
    target = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if target in ('comico', 'all'):
        await debug_comico()
    if target in ('lezhin', 'all'):
        await debug_lezhin()
    if target in ('unext', 'all'):
        await debug_unext()


asyncio.run(main())
