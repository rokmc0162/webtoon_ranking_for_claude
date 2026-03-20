"""Asura 사이트 DOM 구조 분석"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # 메인 페이지
        await page.goto('https://asuracomic.net/', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)

        # Popular 섹션 구조 분석
        print("=== Popular 섹션 HTML 구조 ===")
        popular_html = await page.evaluate("""() => {
            // 'Popular' 텍스트를 포함하는 섹션 찾기
            const headings = document.querySelectorAll('h2, h3, div');
            for (const h of headings) {
                if (h.textContent.trim() === 'Popular') {
                    const section = h.closest('div.bg-\\\\[\\\\#222222\\\\]') ||
                                   h.closest('aside') ||
                                   h.parentElement?.parentElement;
                    if (section) return section.innerHTML.substring(0, 5000);
                }
            }
            return 'NOT FOUND';
        }""")
        print(popular_html[:3000])

        print("\n\n=== 탭 버튼들 ===")
        tabs = await page.evaluate("""() => {
            const buttons = document.querySelectorAll('button');
            const tabs = [];
            for (const btn of buttons) {
                const t = btn.textContent.trim();
                if (['Weekly', 'Monthly', 'All'].includes(t)) {
                    tabs.push({
                        text: t,
                        class: btn.className,
                        parent_tag: btn.parentElement?.tagName,
                        parent_class: btn.parentElement?.className?.substring(0, 100),
                    });
                }
            }
            return tabs;
        }""")
        for t in tabs:
            print(f"  {t}")

        print("\n\n=== Popular 아이템 상세 구조 (첫 번째) ===")
        first_item = await page.evaluate("""() => {
            // Popular 섹션 내부의 시리즈 링크
            const allLinks = document.querySelectorAll('a[href*="/series/"]');
            const popular_links = [];

            for (const link of allLinks) {
                // Popular 섹션 내부인지 확인
                const parent = link.closest('div');
                if (parent) {
                    const siblings = parent.parentElement?.textContent || '';
                    if (siblings.includes('Popular') || siblings.includes('Weekly')) {
                        popular_links.push(link);
                    }
                }
            }

            if (popular_links.length > 0) {
                const link = popular_links[0];
                return {
                    outerHTML: link.outerHTML.substring(0, 1000),
                    parent_html: link.parentElement?.outerHTML?.substring(0, 1500),
                    href: link.getAttribute('href'),
                    text: link.textContent.trim().substring(0, 200),
                };
            }
            return 'NO POPULAR ITEMS';
        }""")
        print(first_item)

        # Trending/Popular 섹션의 정확한 구조
        print("\n\n=== 메인 페이지 섹션 매핑 ===")
        sections = await page.evaluate("""() => {
            const result = [];
            const h2s = document.querySelectorAll('h2, h3');
            for (const h of h2s) {
                result.push({
                    tag: h.tagName,
                    text: h.textContent.trim().substring(0, 50),
                    class: h.className?.substring(0, 100),
                    parent_class: h.parentElement?.className?.substring(0, 100),
                });
            }
            return result;
        }""")
        for s in sections:
            print(f"  <{s['tag']}> {s['text']} (class={s.get('class', '')})")

        await browser.close()

asyncio.run(main())
