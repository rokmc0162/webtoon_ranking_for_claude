"""레진 API cursor pagination 디버그"""
import asyncio
import json
from playwright.async_api import async_playwright


async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto('https://lezhin.jp/ranking', wait_until='domcontentloaded', timeout=20000)
        await page.wait_for_timeout(3000)

        # Get genres
        genres = await page.evaluate("""async () => {
            const resp = await fetch('/api/genres?type=genre_rank');
            const data = await resp.json();
            return data?.results?.data || [];
        }""")
        print(f'Genres: {len(genres)}')
        total_hash = genres[0]['hash_id'] if genres else ''
        print(f'Total genre hash: {total_hash}')

        # First API call
        result = await page.evaluate("""async (genreHash) => {
            const resp = await fetch('/api/ranking?genre_hash_id=' + genreHash + '&type=daily');
            const data = await resp.json();
            return data;
        }""", total_hash)

        results = result.get('results', {})
        data = results.get('data', [])
        cursor = results.get('cursor', '')
        print(f'\nFirst call:')
        print(f'  Data count: {len(data)}')
        print(f'  Cursor: [{cursor}]')
        print(f'  Results keys: {list(results.keys())}')
        if data:
            print(f'  First: rank={data[0].get("rank")}, title={data[0].get("comic", {}).get("name", "?")}')
            print(f'  Last: rank={data[-1].get("rank")}, title={data[-1].get("comic", {}).get("name", "?")}')

        # Second API call with cursor
        if cursor:
            result2 = await page.evaluate("""async (args) => {
                const [genreHash, cursor] = args;
                const resp = await fetch('/api/ranking?genre_hash_id=' + genreHash + '&type=daily&cursor=' + cursor);
                const data = await resp.json();
                return data;
            }""", [total_hash, cursor])

            results2 = result2.get('results', {})
            data2 = results2.get('data', [])
            cursor2 = results2.get('cursor', '')
            print(f'\nSecond call (with cursor):')
            print(f'  Data count: {len(data2)}')
            print(f'  Cursor: [{cursor2}]')
            if data2:
                print(f'  First: rank={data2[0].get("rank")}, title={data2[0].get("comic", {}).get("name", "?")}')
                print(f'  Last: rank={data2[-1].get("rank")}, title={data2[-1].get("comic", {}).get("name", "?")}')
        else:
            print('\nNo cursor returned! Checking full response structure...')
            print(json.dumps(result, indent=2, ensure_ascii=False)[:1000])

        await browser.close()


asyncio.run(test())
