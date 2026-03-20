"""U-NEXT: route intercept로 page 파라미터 변경"""
import asyncio
import json
import urllib.parse
from playwright.async_api import async_playwright


async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        all_books = []
        current_page_target = 1

        async def intercept_ranking_response(response):
            if 'cosmo_getBookRanking' in response.url:
                try:
                    body = await response.json()
                    books = body.get('data', {}).get('bookRanking', {}).get('books', [])
                    for book in books:
                        s = book.get('bookSakuhin', {})
                        all_books.append({
                            'name': s.get('name', ''),
                            'code': s.get('sakuhinCode', ''),
                            'thumb': s.get('book', {}).get('thumbnailUrl', ''),
                        })
                    print(f'  Captured page response: {len(books)} books (total: {len(all_books)})')
                except Exception as e:
                    print(f'  Error parsing response: {e}')

        page.on('response', intercept_ranking_response)

        # Route intercept to modify page parameter
        async def modify_request(route):
            url = route.request.url
            if 'cosmo_getBookRanking' in url and current_page_target > 1:
                # Replace page:1 with current target page
                parsed = urllib.parse.urlparse(url)
                params = urllib.parse.parse_qs(parsed.query)
                if 'variables' in params:
                    variables = json.loads(params['variables'][0])
                    variables['page'] = current_page_target
                    params['variables'] = [json.dumps(variables)]
                    # Reconstruct URL
                    new_query = urllib.parse.urlencode({k: v[0] for k, v in params.items()})
                    new_url = f'{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}'
                    await route.continue_(url=new_url)
                    return
            await route.continue_()

        await page.route('**/cc.unext.jp/**', modify_request)

        # Page 1: normal load
        print('Loading page 1...')
        await page.goto('https://video.unext.jp/book/ranking/comic', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(8000)
        print(f'After page 1: {len(all_books)} books total')

        # Pages 2-5: reload the page with route intercept changing the page number
        for pg in range(2, 6):
            current_page_target = pg
            print(f'Loading page {pg}...')
            await page.goto('https://video.unext.jp/book/ranking/comic', wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(5000)
            print(f'After page {pg}: {len(all_books)} books total')

        # Dedup
        seen = set()
        unique = []
        for b in all_books:
            if b['name'] and b['name'] not in seen:
                seen.add(b['name'])
                unique.append(b)

        print(f'\nTotal unique: {len(unique)} books')
        with_thumb = sum(1 for b in unique if b.get('thumb'))
        print(f'With thumbnails: {with_thumb}')
        for i, b in enumerate(unique[:5]):
            print(f'  {i+1}. {b["name"][:40]}')
        if len(unique) >= 100:
            print(f'  ...')
            print(f'  100. {unique[99]["name"][:40]}')

        await browser.close()


asyncio.run(test())
