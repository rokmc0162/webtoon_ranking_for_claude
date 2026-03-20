"""U-NEXT: 정확한 URL 구조 분석 + 재현"""
import asyncio
import json
import urllib.parse
from playwright.async_api import async_playwright


async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        captured_data = {}

        async def capture(response):
            if 'cosmo_getBookRanking' in response.url:
                captured_data['url'] = response.url
                captured_data['req_url'] = response.request.url
                # Parse URL params
                parsed = urllib.parse.urlparse(response.url)
                params = urllib.parse.parse_qs(parsed.query)
                captured_data['params'] = {k: v[0] for k, v in params.items()}
                try:
                    body = await response.json()
                    captured_data['response'] = body
                except:
                    pass

        page.on('response', capture)
        await page.goto('https://video.unext.jp/book/ranking/comic', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(8000)

        if not captured_data:
            print('No GraphQL call captured!')
            return

        params = captured_data['params']
        print("URL Parameters:")
        for k, v in params.items():
            val = v if len(v) < 100 else v[:100] + '...'
            print(f"  {k} = {val}")

        # Exact reconstruct: change only variables.page
        orig_variables = json.loads(params['variables'])
        orig_extensions = params['extensions']
        base_url = f"https://cc.unext.jp/?zxuid={params['zxuid']}&zxemp={params['zxemp']}"

        print(f"\nOriginal variables: {json.dumps(orig_variables)}")
        print(f"Extensions length: {len(orig_extensions)}")

        all_books = []

        for pg in range(1, 6):
            new_vars = dict(orig_variables)
            new_vars['page'] = pg
            fetch_url = (
                f"{base_url}"
                f"&operationName={params['operationName']}"
                f"&variables={urllib.parse.quote(json.dumps(new_vars))}"
                f"&extensions={urllib.parse.quote(orig_extensions)}"
            )

            result = await page.evaluate("""async (fetchUrl) => {
                try {
                    const resp = await fetch(fetchUrl, {credentials: 'include'});
                    const text = await resp.text();
                    if (!resp.ok) return {error: resp.status, body: text.substring(0, 200)};
                    const data = JSON.parse(text);
                    const ranking = data?.data?.bookRanking || {};
                    const books = ranking.books || [];
                    return {
                        count: books.length,
                        books: books.map(b => ({
                            name: (b?.bookSakuhin?.name || ''),
                            code: b?.bookSakuhin?.sakuhinCode || '',
                            thumb: b?.bookSakuhin?.book?.thumbnailUrl || '',
                        }))
                    };
                } catch(e) {
                    return {error: e.message};
                }
            }""", fetch_url)

            if 'error' in result:
                print(f'Page {pg}: ERROR - {result.get("error")}, body: {result.get("body", "")[:100]}')
            else:
                books = result.get('books', [])
                print(f'Page {pg}: {result["count"]} books, first: {books[0]["name"][:30] if books else "?"}')
                all_books.extend(books)

        print(f'\nTotal: {len(all_books)} books')
        with_thumb = sum(1 for b in all_books if b.get('thumb'))
        print(f'With thumbnails: {with_thumb}')

        await browser.close()


asyncio.run(test())
