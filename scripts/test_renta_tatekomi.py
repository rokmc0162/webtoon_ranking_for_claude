"""렌타 タテコミ 크롤링 단독 테스트"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright

async def main():
    from crawler.agents.renta_agent import RentaAgent

    agent = RentaAgent()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        try:
            result = await agent.execute(browser)
            print(f"\n=== 결과 ===")
            print(f"성공: {result.success}")
            print(f"작품 수: {result.count}")
            print(f"시도: {result.attempts}")
            if result.error:
                print(f"에러: {result.error}")

            # genre_results 확인
            print(f"\n=== genre_results ===")
            for key, rankings in agent.genre_results.items():
                label = agent.GENRE_RANKINGS.get(key, {}).get('name', key)
                print(f"  [{label}]: {len(rankings)}개")
                if rankings:
                    print(f"    1위: {rankings[0]['title']}")
                    if len(rankings) > 1:
                        print(f"    2위: {rankings[1]['title']}")

        finally:
            await browser.close()

asyncio.run(main())
