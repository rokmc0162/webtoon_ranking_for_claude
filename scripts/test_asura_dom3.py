"""Asura Popular 섹션 정밀 분석 (v3)"""
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

        # 1. Popular 섹션의 아이템 구조
        print("=== Popular 사이드바 아이템 ===")
        items = await page.evaluate("""() => {
            const results = [];
            const h3s = document.querySelectorAll('h3');
            let popularH3 = null;
            for (const h of h3s) {
                if (h.textContent.trim() === 'Popular') {
                    popularH3 = h;
                    break;
                }
            }
            if (!popularH3) return ['Popular h3 not found'];

            // 상위 3단계까지 올라가기
            let container = popularH3.parentElement;
            for (let i = 0; i < 5; i++) {
                if (!container) break;
                const links = container.querySelectorAll('a[href*="/series/"]');
                if (links.length >= 5) {
                    // 이 컨테이너에서 추출
                    for (let j = 0; j < Math.min(links.length, 12); j++) {
                        const link = links[j];
                        results.push({
                            idx: j,
                            href: link.getAttribute('href'),
                            text: link.innerText.replace(/\\n/g, ' | ').substring(0, 150),
                        });
                    }
                    break;
                }
                container = container.parentElement;
            }
            return results;
        }""")
        for item in items:
            if isinstance(item, str):
                print(f"  {item}")
            else:
                print(f"  [{item['idx']}] {item['text'][:80]}")
                print(f"       → {item['href']}")

        # 2. 탭 상태 확인
        print("\n=== 탭 상태 ===")
        tab_state = await page.evaluate("""() => {
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
        for s in tab_state:
            print(f"  {s['text']}: data-state={s['data_state']}")

        # 3. tabpanel 구조 확인
        print("\n=== tabpanel 구조 ===")
        panels = await page.evaluate("""() => {
            const panels = document.querySelectorAll('[role="tabpanel"]');
            return Array.from(panels).map(p => ({
                data_state: p.getAttribute('data-state'),
                class: p.className?.substring(0, 100),
                links_count: p.querySelectorAll('a[href*="/series/"]').length,
                first_link_text: p.querySelector('a[href*="/series/"]')?.innerText?.substring(0, 60),
            }));
        }""")
        for panel in panels:
            print(f"  state={panel['data_state']}, links={panel['links_count']}, first={panel.get('first_link_text', 'N/A')}")

        # 4. Monthly 탭 클릭 후
        print("\n=== Monthly 탭 클릭 ===")
        monthly_btn = await page.query_selector('button:has-text("Monthly")')
        if monthly_btn:
            await monthly_btn.click()
            await page.wait_for_timeout(2000)

            panels2 = await page.evaluate("""() => {
                const panels = document.querySelectorAll('[role="tabpanel"]');
                return Array.from(panels).map(p => ({
                    data_state: p.getAttribute('data-state'),
                    links_count: p.querySelectorAll('a[href*="/series/"]').length,
                    first_link_text: p.querySelector('a[href*="/series/"]')?.innerText?.replace(/\\n/g,' ').substring(0, 60),
                }));
            }""")
            for panel in panels2:
                print(f"  state={panel['data_state']}, links={panel['links_count']}, first={panel.get('first_link_text', 'N/A')}")

        # 5. All 탭 클릭 후
        print("\n=== All 탭 클릭 ===")
        all_btn = await page.query_selector('button:has-text("All")')
        if all_btn:
            await all_btn.click()
            await page.wait_for_timeout(2000)

            panels3 = await page.evaluate("""() => {
                const panels = document.querySelectorAll('[role="tabpanel"]');
                return Array.from(panels).map(p => ({
                    data_state: p.getAttribute('data-state'),
                    links_count: p.querySelectorAll('a[href*="/series/"]').length,
                    first_link_text: p.querySelector('a[href*="/series/"]')?.innerText?.replace(/\\n/g,' ').substring(0, 60),
                }));
            }""")
            for panel in panels3:
                print(f"  state={panel['data_state']}, links={panel['links_count']}, first={panel.get('first_link_text', 'N/A')}")

        await browser.close()

asyncio.run(main())
