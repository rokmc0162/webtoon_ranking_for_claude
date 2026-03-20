"""Asura Popular 섹션 정밀 분석"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto('https://asuracomic.net/', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)

        # Popular 섹션 (사이드바) 내부 아이템 추출
        print("=== Popular (사이드바) 섹션 - Weekly 탭 ===")
        items = await page.evaluate("""() => {
            const results = [];
            // Popular h3 찾기
            const h3s = document.querySelectorAll('h3');
            let popularH3 = null;
            for (const h of h3s) {
                if (h.textContent.trim() === 'Popular') {
                    popularH3 = h;
                    break;
                }
            }
            if (!popularH3) return ['Popular h3 not found'];

            // Popular h3의 부모 컨테이너
            const container = popularH3.closest('div.bg-\\\\[#222222\\\\]') ||
                             popularH3.parentElement?.parentElement?.parentElement;

            if (!container) return ['Container not found'];

            // 이 컨테이너 안의 시리즈 링크
            const links = container.querySelectorAll('a[href*="/series/"]');

            for (let i = 0; i < Math.min(links.length, 3); i++) {
                const link = links[i];
                results.push({
                    href: link.getAttribute('href'),
                    outerHTML: link.outerHTML.substring(0, 2000),
                    innerText: link.innerText.substring(0, 200),
                    childrenTags: Array.from(link.children).map(c => c.tagName + '.' + c.className?.substring(0, 50)),
                });
            }
            return results;
        }""")
        for i, item in enumerate(items):
            print(f"\n--- 아이템 {i+1} ---")
            if isinstance(item, str):
                print(item)
            else:
                print(f"href: {item.get('href')}")
                print(f"innerText: {item.get('innerText')}")
                print(f"children: {item.get('childrenTags')}")

        # Popular Today 섹션 (메인 트렌딩)
        print("\n\n=== Popular Today 섹션 ===")
        trending = await page.evaluate("""() => {
            const results = [];
            const h3s = document.querySelectorAll('h3');
            let todayH3 = null;
            for (const h of h3s) {
                if (h.textContent.trim() === 'Popular Today') {
                    todayH3 = h;
                    break;
                }
            }
            if (!todayH3) return ['Popular Today h3 not found'];

            const container = todayH3.parentElement?.parentElement;
            if (!container) return ['Container not found'];

            const links = container.querySelectorAll('a[href*="/series/"]');
            for (let i = 0; i < Math.min(links.length, 5); i++) {
                const link = links[i];
                // 순위 번호 찾기
                const numEl = link.querySelector('span.text-themecolor, span.font-bold');
                const num = numEl ? numEl.textContent.trim() : '';

                results.push({
                    rank_num: num,
                    href: link.getAttribute('href'),
                    innerText: link.innerText.substring(0, 150),
                    html_preview: link.innerHTML.substring(0, 500),
                });
            }
            return results;
        }""")
        for i, item in enumerate(trending):
            print(f"\n--- Trending {i+1} ---")
            if isinstance(item, str):
                print(item)
            else:
                print(f"rank: {item.get('rank_num')}")
                print(f"href: {item.get('href')}")
                print(f"innerText: {item.get('innerText')[:100]}")

        # Weekly 탭 클릭 후 Popular 내용
        print("\n\n=== Weekly 탭 활성 여부 체크 ===")
        tab_state = await page.evaluate("""() => {
            const buttons = document.querySelectorAll('button');
            const states = [];
            for (const btn of buttons) {
                const t = btn.textContent.trim();
                if (['Weekly', 'Monthly', 'All'].includes(t)) {
                    states.push({
                        text: t,
                        data_state: btn.getAttribute('data-state'),
                        aria_selected: btn.getAttribute('aria-selected'),
                    });
                }
            }
            return states;
        }""")
        for s in tab_state:
            print(f"  {s}")

        # Monthly 탭 클릭
        print("\n\n=== Monthly 탭 클릭 후 ===")
        monthly_btn = await page.query_selector('button:has-text("Monthly")')
        if monthly_btn:
            await monthly_btn.click()
            await page.wait_for_timeout(2000)

            tab_state2 = await page.evaluate("""() => {
                const buttons = document.querySelectorAll('button');
                const states = [];
                for (const btn of buttons) {
                    const t = btn.textContent.trim();
                    if (['Weekly', 'Monthly', 'All'].includes(t)) {
                        states.push({
                            text: t,
                            data_state: btn.getAttribute('data-state'),
                        });
                    }
                }
                return states;
            }""")
            for s in tab_state2:
                print(f"  {s}")

            # Monthly 탭에서의 첫 번째 아이템
            monthly_items = await page.evaluate("""() => {
                const h3s = document.querySelectorAll('h3');
                let popularH3 = null;
                for (const h of h3s) {
                    if (h.textContent.trim() === 'Popular') {
                        popularH3 = h;
                        break;
                    }
                }
                if (!popularH3) return [];

                const container = popularH3.parentElement?.parentElement?.parentElement;
                if (!container) return [];

                // data-state=active인 탭패널 찾기
                const panels = container.querySelectorAll('[role="tabpanel"], [data-state="active"]');
                for (const panel of panels) {
                    const links = panel.querySelectorAll('a[href*="/series/"]');
                    if (links.length > 0) {
                        return Array.from(links).slice(0, 3).map(l => ({
                            href: l.getAttribute('href'),
                            text: l.innerText.substring(0, 100),
                        }));
                    }
                }

                // 폴백: 직접 탐색
                const links = container.querySelectorAll('a[href*="/series/"]');
                return Array.from(links).slice(0, 3).map(l => ({
                    href: l.getAttribute('href'),
                    text: l.innerText.substring(0, 100),
                }));
            }""")
            for item in monthly_items:
                print(f"  {item.get('text', '')[:60]} → {item.get('href')}")

        await browser.close()

asyncio.run(main())
