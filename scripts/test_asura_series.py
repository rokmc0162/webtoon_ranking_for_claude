"""Asura 시리즈 목록 페이지 디버깅"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://asuracomic.net/series?page=1&order=popular',
                        wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)

        # 모든 시리즈 링크 분석
        items = await page.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="/series/"]');
            return Array.from(links).slice(0, 30).map(l => {
                const text = l.innerText.replace(/\\n/g, ' | ').trim();
                const parent = l.closest('div');
                const parentText = parent ? parent.textContent.replace(/\\n/g, ' ').substring(0, 200) : '';

                return {
                    href: l.getAttribute('href'),
                    text: text.substring(0, 120),
                    hasImg: !!l.querySelector('img'),
                    parentPreview: parentText.substring(0, 150),
                };
            });
        }""")

        print(f'총 {len(items)}개 링크')
        for i, item in enumerate(items):
            tag = '[IMG]' if item['hasImg'] else '[TXT]'
            print(f'  [{i}] {tag} text="{item["text"][:60]}"')
            print(f'       href={item["href"]}')

        # 시리즈 카드 구조 분석
        print("\n\n=== 시리즈 카드 구조 ===")
        card_html = await page.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="/series/"]');
            for (const link of links) {
                if (link.querySelector('img') && link.innerText.trim().length > 5) {
                    return {
                        outerHTML: link.outerHTML.substring(0, 2000),
                        innerText: link.innerText.substring(0, 300),
                    };
                }
            }
            // 이미지가 있는 첫 번째 링크
            for (const link of links) {
                if (link.querySelector('img')) {
                    const parent = link.parentElement;
                    return {
                        outerHTML: link.outerHTML.substring(0, 1500),
                        parentHTML: parent ? parent.outerHTML.substring(0, 2000) : 'N/A',
                        innerText: link.innerText.substring(0, 300),
                    };
                }
            }
            return 'No cards found';
        }""")
        if isinstance(card_html, dict):
            print(f"innerText: {card_html.get('innerText', '')[:200]}")
            print(f"outerHTML preview: {card_html.get('outerHTML', '')[:500]}")
        else:
            print(card_html)

        await browser.close()

asyncio.run(main())
