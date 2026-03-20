"""U-NEXT 페이지 2-5 가져오기 테스트"""
import asyncio
import json
import urllib.parse
from playwright.async_api import async_playwright


async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        gql_data = {}

        async def capture(response):
            if 'cosmo_getBookRanking' in response.url:
                try:
                    body = await response.json()
                    books = body.get('data', {}).get('bookRanking', {}).get('books', [])
                    page_info = body.get('data', {}).get('bookRanking', {}).get('pageInfo', {})
                    gql_data['url'] = response.url
                    gql_data['books'] = books
                    gql_data['pageInfo'] = page_info
                except:
                    pass

        page.on('response', capture)
        await page.goto('https://video.unext.jp/book/ranking/comic', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(8000)

        if not gql_data:
            print('No GraphQL call captured!')
            return

        url = gql_data['url']
        print(f'Page 1: {len(gql_data["books"])} books')
        print(f'PageInfo: {gql_data["pageInfo"]}')
        print(f'First: {gql_data["books"][0]["bookSakuhin"]["name"]}')

        # Parse URL
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        variables = json.loads(params.get('variables', ['{}'])[0])
        extensions = params.get('extensions', [''])[0]
        op_name = params.get('operationName', [''])[0]
        zxuid = params.get('zxuid', [''])[0]
        zxemp = params.get('zxemp', [''])[0]

        all_books = list(gql_data['books'])

        for pg in range(2, 6):
            variables['page'] = pg
            new_url = (
                f'{parsed.scheme}://{parsed.netloc}{parsed.path}'
                f'?zxuid={zxuid}&zxemp={zxemp}'
                f'&operationName={op_name}'
                f'&variables={urllib.parse.quote(json.dumps(variables))}'
                f'&extensions={urllib.parse.quote(extensions)}'
            )

            result = await page.evaluate("""async (fetchUrl) => {
                try {
                    const resp = await fetch(fetchUrl, {credentials: 'include'});
                    if (!resp.ok) return {error: resp.status};
                    const data = await resp.json();
                    const books = data?.data?.bookRanking?.books || [];
                    return {
                        count: books.length,
                        books: books.map(b => ({
                            name: b?.bookSakuhin?.name || '',
                            code: b?.bookSakuhin?.sakuhinCode || '',
                            thumb: b?.bookSakuhin?.book?.thumbnailUrl || '',
                        }))
                    };
                } catch(e) {
                    return {error: e.message};
                }
            }""", new_url)

            if 'error' in result:
                print(f'Page {pg}: ERROR - {result["error"]}')
            else:
                print(f'Page {pg}: {result["count"]} books, first: {result["books"][0]["name"] if result["books"] else "?"}')
                all_books.extend([{'bookSakuhin': {'name': b['name'], 'sakuhinCode': b['code'], 'book': {'thumbnailUrl': b['thumb']}}} for b in result.get('books', [])])

        print(f'\nTotal: {len(all_books)} books')
        with_thumb = sum(1 for b in all_books if b.get('bookSakuhin', {}).get('book', {}).get('thumbnailUrl'))
        print(f'With thumbnails: {with_thumb}')

        await browser.close()


asyncio.run(test())
