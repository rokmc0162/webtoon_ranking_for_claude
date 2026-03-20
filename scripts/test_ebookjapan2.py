"""ebookjapan scroll + thumbnail count test"""
import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://ebookjapan.yahoo.co.jp/ranking/', wait_until='domcontentloaded', timeout=20000)
        await page.wait_for_timeout(5000)

        # Click more button
        try:
            more_btn = await page.query_selector('a:has-text("もっと見る")')
            if more_btn:
                await more_btn.click()
                await page.wait_for_timeout(3000)
                print('Clicked more button')
        except:
            pass

        # Scroll to trigger lazy loading
        for _ in range(8):
            await page.evaluate('window.scrollBy(0, 800)')
            await page.wait_for_timeout(500)

        # Count loaded thumbnails
        count = await page.evaluate("""() => {
            const imgs = document.querySelectorAll('img.cover-main__img');
            let loaded = 0;
            const titles = [];
            for (const img of imgs) {
                const src = img.getAttribute('src') || '';
                if (src.startsWith('http') && !src.includes('loading-book-cover')) {
                    loaded++;
                    titles.push((img.getAttribute('alt') || '').substring(0, 30));
                }
            }
            return {loaded, total: imgs.length, titles: titles.slice(0, 10)};
        }""")
        print(f'Total cover-main imgs: {count["total"]}, loaded with real URL: {count["loaded"]}')
        print(f'First 10 titles: {count["titles"]}')

        await browser.close()

asyncio.run(test())
