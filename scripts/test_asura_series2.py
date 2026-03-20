"""Asura 시리즈 그리드 카드 분석"""
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

        # 메인 콘텐츠 영역의 구조
        print("=== 페이지 내 주요 컨테이너 구조 ===")
        structure = await page.evaluate("""() => {
            // 모든 img 태그 (시리즈 커버일 가능성)
            const imgs = document.querySelectorAll('img');
            const seriesImgs = [];
            for (const img of imgs) {
                const alt = img.getAttribute('alt') || '';
                const src = img.getAttribute('src') || '';
                if (src.includes('asura') || src.includes('storage')) {
                    const parent = img.closest('a');
                    const href = parent ? parent.getAttribute('href') : 'no-link';
                    seriesImgs.push({
                        alt: alt,
                        src: src.substring(0, 80),
                        parentHref: href,
                        parentTag: parent ? parent.tagName : img.parentElement?.tagName,
                        parentClass: parent ? parent.className?.substring(0, 80) : '',
                    });
                }
            }
            return seriesImgs;
        }""")
        print(f"시리즈 이미지: {len(structure)}개")
        for i, s in enumerate(structure[:10]):
            print(f"  [{i}] alt={s['alt'][:30]}, href={s['parentHref']}, class={s['parentClass'][:50]}")

        # grid/flex 컨테이너 찾기
        print("\n\n=== Grid 컨테이너 ===")
        grids = await page.evaluate("""() => {
            const grids = document.querySelectorAll('[class*="grid"]');
            return Array.from(grids).slice(0, 10).map(g => ({
                tag: g.tagName,
                class: g.className?.substring(0, 120),
                childCount: g.children.length,
                firstChildTag: g.children[0]?.tagName,
                firstChildClass: g.children[0]?.className?.substring(0, 80),
                hasSeriesLinks: g.querySelectorAll('a[href*="/series/"]').length,
            }));
        }""")
        for g in grids:
            if g['hasSeriesLinks'] > 0:
                print(f"  <{g['tag']}> class={g['class'][:80]}")
                print(f"    children={g['childCount']}, seriesLinks={g['hasSeriesLinks']}")

        # 메인 그리드 카드 상세 구조
        print("\n\n=== 메인 그리드 카드 HTML ===")
        card = await page.evaluate("""() => {
            const grids = document.querySelectorAll('[class*="grid"]');
            for (const grid of grids) {
                const links = grid.querySelectorAll('a[href*="/series/"]');
                // 15개 이상의 시리즈 링크가 있는 그리드 = 메인 그리드
                if (links.length >= 15) {
                    // 첫 번째 자식 (카드)의 HTML
                    const firstChild = grid.children[0];
                    if (firstChild) {
                        return {
                            gridClass: grid.className?.substring(0, 120),
                            cardHTML: firstChild.outerHTML?.substring(0, 3000),
                            cardText: firstChild.innerText?.substring(0, 300),
                        };
                    }
                }
            }
            return 'Grid not found';
        }""")
        if isinstance(card, dict):
            print(f"Grid class: {card.get('gridClass', '')[:100]}")
            print(f"Card text: {card.get('cardText', '')[:200]}")
            print(f"Card HTML:\n{card.get('cardHTML', '')[:1500]}")
        else:
            print(card)

        await browser.close()

asyncio.run(main())
