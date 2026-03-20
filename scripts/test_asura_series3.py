"""Asura 시리즈 그리드 카드 - href 패턴 수정"""
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

        # 모든 href에 "series/" 포함되는 a 태그 (/ 없이도)
        print("=== 모든 series 링크 (href 패턴 넓힘) ===")
        items = await page.evaluate("""() => {
            const allLinks = document.querySelectorAll('a');
            const results = [];
            for (const link of allLinks) {
                const href = link.getAttribute('href') || '';
                if (href.includes('series/') && href.match(/[a-z].*-[a-f0-9]{6,}/)) {
                    results.push({
                        href: href,
                        text: link.innerText.replace(/\\n/g, ' | ').trim().substring(0, 120),
                        hasImg: !!link.querySelector('img'),
                        parentTag: link.parentElement?.tagName,
                        parentClass: link.parentElement?.className?.substring(0, 80),
                    });
                }
            }
            return results;
        }""")
        print(f"총 {len(items)}개 링크")

        # /series/ vs series/ 패턴 분리
        with_slash = [i for i in items if i['href'].startswith('/series/')]
        without_slash = [i for i in items if not i['href'].startswith('/series/')]

        print(f"\n/series/ 패턴: {len(with_slash)}개 (사이드바)")
        for i in with_slash[:5]:
            tag = '[IMG]' if i['hasImg'] else '[TXT]'
            print(f"  {tag} {i['text'][:50]} → {i['href'][:50]}")

        print(f"\nseries/ 패턴 (슬래시 없음): {len(without_slash)}개 (메인 그리드)")
        for i in without_slash[:20]:
            tag = '[IMG]' if i['hasImg'] else '[TXT]'
            print(f"  {tag} parent={i['parentTag']}.{i['parentClass'][:30]}")
            print(f"       text={i['text'][:60]}")
            print(f"       href={i['href'][:60]}")

        # 메인 그리드 카드의 상위 구조
        if without_slash:
            print("\n\n=== 첫 번째 메인 그리드 카드 HTML ===")
            first_href = without_slash[0]['href']
            card_html = await page.evaluate("""(href) => {
                const links = document.querySelectorAll('a');
                for (const link of links) {
                    if (link.getAttribute('href') === href) {
                        // 카드 컨테이너 찾기 (여러 레벨 위)
                        let container = link;
                        for (let i = 0; i < 5; i++) {
                            container = container.parentElement;
                            if (!container) break;
                            // 형제 요소가 있으면 그리드 아이템 가능성
                            if (container.parentElement && container.parentElement.children.length > 5) {
                                return {
                                    cardHTML: container.outerHTML.substring(0, 3000),
                                    cardText: container.innerText.substring(0, 500),
                                    gridParentClass: container.parentElement.className?.substring(0, 120),
                                    gridChildCount: container.parentElement.children.length,
                                };
                            }
                        }
                        return {
                            linkHTML: link.outerHTML.substring(0, 1000),
                            parentHTML: link.parentElement?.outerHTML?.substring(0, 2000),
                        };
                    }
                }
                return 'not found';
            }""", first_href)

            if isinstance(card_html, dict):
                print(f"gridParentClass: {card_html.get('gridParentClass', 'N/A')}")
                print(f"gridChildCount: {card_html.get('gridChildCount', 'N/A')}")
                print(f"cardText:\n{card_html.get('cardText', '')[:400]}")
            else:
                print(card_html)

        await browser.close()

asyncio.run(main())
