"""ebookjapan DOM structure 디버그"""
import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://ebookjapan.yahoo.co.jp/ranking/', wait_until='domcontentloaded', timeout=20000)
        await page.wait_for_timeout(5000)

        # Try more_btn
        try:
            more_btn = await page.query_selector('a:has-text("もっと見る")')
            if more_btn:
                await more_btn.click()
                await page.wait_for_timeout(3000)
                print('Clicked more button')
        except:
            pass

        # Check what images exist
        imgs = await page.evaluate("""() => {
            const imgs = document.querySelectorAll('img');
            const results = [];
            for (const img of imgs) {
                const src = img.getAttribute('src') || '';
                const alt = img.getAttribute('alt') || '';
                const cls = img.getAttribute('class') || '';
                if (src && !src.includes('data:image') && !src.includes('logo') && alt.length > 2) {
                    results.push({src: src.substring(0,100), alt: alt.substring(0,50), cls: cls});
                }
            }
            return results.slice(0, 20);
        }""")

        print(f'Found {len(imgs)} images with alt text (first 20):')
        for i, img in enumerate(imgs):
            print(f'  {i+1}. cls=[{img["cls"]}] alt=[{img["alt"]}] src=[{img["src"]}]')

        # Check for cover-main__img specifically
        cover_count = await page.evaluate('document.querySelectorAll("img.cover-main__img").length')
        print(f'\ncover-main__img count: {cover_count}')

        # Check list items
        li_count = await page.evaluate('document.querySelectorAll("li.contents-list__item").length')
        print(f'contents-list__item count: {li_count}')

        # Check rankings list
        ranking_ul = await page.evaluate('document.querySelectorAll("ul.contents-ranking__list").length')
        print(f'contents-ranking__list count: {ranking_ul}')

        # Try broader selectors for any img inside ranking containers
        items = await page.evaluate("""() => {
            const results = [];
            const all = document.querySelectorAll('[class*="ranking"], [class*="cover"], [class*="book-item"]');
            for (const el of all) {
                const imgs = el.querySelectorAll('img');
                if (imgs.length > 0) {
                    for (const img of imgs) {
                        const src = img.getAttribute('src') || '';
                        if (src && !src.includes('data:image')) {
                            results.push({
                                parentTag: el.tagName,
                                parentCls: (el.className || '').substring(0, 80),
                                imgSrc: src.substring(0, 80),
                                imgAlt: (img.getAttribute('alt') || '').substring(0, 40),
                                imgCls: img.getAttribute('class') || ''
                            });
                        }
                    }
                }
            }
            return results.slice(0, 15);
        }""")
        print(f'\nImages inside ranking/cover/book containers:')
        for item in items:
            print(f'  {item["parentTag"]}.{item["parentCls"]}')
            print(f'    img cls=[{item["imgCls"]}] alt=[{item["imgAlt"]}]')
            print(f'    src=[{item["imgSrc"]}]')

        # Get actual page content snippet for debugging
        snippet = await page.evaluate("""() => {
            const body = document.body.innerHTML;
            // Find first occurrence of ranking-related content
            const idx = body.indexOf('ranking');
            if (idx > -1) {
                return body.substring(Math.max(0, idx - 100), idx + 500);
            }
            return body.substring(0, 500);
        }""")
        print(f'\nPage HTML snippet around "ranking":')
        print(snippet[:400])

        await browser.close()

asyncio.run(test())
