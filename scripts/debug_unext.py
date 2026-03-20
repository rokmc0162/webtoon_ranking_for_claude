"""U-NEXT GraphQL 네트워크 분석"""
import asyncio
import json
from playwright.async_api import async_playwright


async def debug_unext():
    print("=== U-NEXT 네트워크 분석 ===")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        graphql_calls = []

        async def handle_response(response):
            url = response.url
            if 'cc.unext.jp' in url or 'graphql' in url.lower():
                try:
                    body = await response.json()
                    # Extract request info
                    req = response.request
                    post_data = req.post_data or ''
                    graphql_calls.append({
                        'url': url[:150],
                        'status': response.status,
                        'req_headers': dict(req.headers),
                        'post_data': post_data[:500] if post_data else '',
                        'resp_sample': json.dumps(body, ensure_ascii=False)[:500]
                    })
                except:
                    pass

        page.on('response', handle_response)

        await page.goto('https://video.unext.jp/book/ranking/comic', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(8000)

        print(f"\nGraphQL 호출: {len(graphql_calls)}개")
        for i, call in enumerate(graphql_calls[:10]):
            print(f"\n  [{i+1}] URL: {call['url']}")
            print(f"      Status: {call['status']}")
            if call.get('post_data'):
                print(f"      POST body: {call['post_data'][:300]}")
            print(f"      Response: {call['resp_sample'][:300]}")
            # Show relevant request headers
            hdrs = call.get('req_headers', {})
            relevant = {k: v for k, v in hdrs.items() if k.lower() in ('content-type', 'authorization', 'x-csrf', 'cookie')}
            if relevant:
                print(f"      Headers: {relevant}")

        # Now try to replicate the GraphQL call from page context
        if graphql_calls:
            print("\n--- 페이지 컨텍스트에서 GraphQL 재현 시도 ---")
            # Extract URL and try to mimic
            gql_url = graphql_calls[0]['url']
            post_data = graphql_calls[0].get('post_data', '')

            if post_data:
                try:
                    parsed = json.loads(post_data)
                    op_name = parsed.get('operationName', '')
                    variables = parsed.get('variables', {})
                    print(f"  Operation: {op_name}")
                    print(f"  Variables: {json.dumps(variables)}")

                    # Try with page 1-5
                    if 'page' in variables:
                        test_result = await page.evaluate("""async (args) => {
                            try {
                                const [url, postBody] = args;
                                const parsed = JSON.parse(postBody);
                                const results = [];

                                for (let p = 1; p <= 5; p++) {
                                    parsed.variables.page = p;
                                    const resp = await fetch(url, {
                                        method: 'POST',
                                        headers: {'content-type': 'application/json'},
                                        body: JSON.stringify(parsed),
                                        credentials: 'include'
                                    });
                                    if (!resp.ok) {
                                        results.push({page: p, error: resp.status});
                                        continue;
                                    }
                                    const data = await resp.json();
                                    // Navigate to books
                                    const books = data?.data?.bookRanking?.books ||
                                                  data?.data?.webfront_bookRanking?.books || [];
                                    const pageInfo = data?.data?.bookRanking?.pageInfo ||
                                                     data?.data?.webfront_bookRanking?.pageInfo || {};
                                    results.push({
                                        page: p,
                                        count: books.length,
                                        pageInfo: pageInfo,
                                        firstTitle: books[0]?.bookSakuhin?.name || 'unknown',
                                        lastTitle: books[books.length-1]?.bookSakuhin?.name || 'unknown',
                                    });
                                }
                                return results;
                            } catch(e) {
                                return {error: e.message};
                            }
                        }""", [gql_url, post_data])
                        print(f"\n  페이지별 결과:")
                        if isinstance(test_result, list):
                            for r in test_result:
                                print(f"    Page {r.get('page')}: {r.get('count', 'error')} items, first: {r.get('firstTitle')}, last: {r.get('lastTitle')}")
                                if r.get('pageInfo'):
                                    print(f"      pageInfo: {r.get('pageInfo')}")
                        else:
                            print(f"    Error: {test_result}")
                except json.JSONDecodeError:
                    print(f"  POST data is not JSON: {post_data[:200]}")

        await browser.close()


asyncio.run(debug_unext())
