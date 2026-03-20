"""U-NEXT: 네트워크 route 인터셉트로 pagination"""
import asyncio
import json
import urllib.parse
from playwright.async_api import async_playwright


async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        captured_url = None

        async def capture(response):
            nonlocal captured_url
            if 'cosmo_getBookRanking' in response.url:
                captured_url = response.url

        page.on('response', capture)
        await page.goto('https://video.unext.jp/book/ranking/comic', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(8000)

        if not captured_url:
            print('No GraphQL call captured!')
            return

        print(f'Captured URL: {captured_url[:200]}...')

        # Build page 2-5 URLs by modifying the variables in the captured URL
        all_books = []

        for pg in range(1, 6):
            # Replace page number in URL
            # The URL has variables=%7B%22targetCode%22%3A%22D_COMIC%22%2C%22page%22%3A1%2C...
            # We need to replace "page":1 with "page":N
            modified_url = captured_url.replace(
                urllib.parse.quote('"page":1,'),
                urllib.parse.quote(f'"page":{pg},')
            )

            result = await page.evaluate("""async (fetchUrl) => {
                try {
                    const resp = await fetch(fetchUrl, {credentials: 'include'});
                    if (!resp.ok) return {error: resp.status, statusText: resp.statusText};
                    const data = await resp.json();
                    const ranking = data?.data?.bookRanking || data?.data?.webfront_bookRanking || {};
                    const books = ranking.books || [];
                    return {
                        count: books.length,
                        pageInfo: ranking.pageInfo || {},
                        books: books.map(b => ({
                            name: (b?.bookSakuhin?.name || '').substring(0, 50),
                            code: b?.bookSakuhin?.sakuhinCode || '',
                            thumb: (b?.bookSakuhin?.book?.thumbnailUrl || '').substring(0, 80),
                        }))
                    };
                } catch(e) {
                    return {error: e.message};
                }
            }""", modified_url)

            if 'error' in result:
                print(f'Page {pg}: ERROR - {result}')
            else:
                books = result.get('books', [])
                print(f'Page {pg}: {result["count"]} books')
                if books:
                    print(f'  First: {books[0]["name"]}')
                    print(f'  Last:  {books[-1]["name"]}')
                    print(f'  Thumb: {books[0]["thumb"][:60]}')
                all_books.extend(books)

        print(f'\nTotal: {len(all_books)} books')
        with_thumb = sum(1 for b in all_books if b.get('thumb'))
        print(f'With thumbnails: {with_thumb}')

        await browser.close()


asyncio.run(test())
