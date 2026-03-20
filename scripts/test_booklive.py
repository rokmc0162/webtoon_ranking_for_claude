"""북라이브 장르별 크롤링 테스트"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright

async def main():
    from crawler.agents.booklive_agent import BookliveAgent

    agent = BookliveAgent()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        try:
            result = await agent.execute(browser)
            print(f"\n=== 결과 ===")
            print(f"성공: {result.success}")
            print(f"작품 수: {result.count}")
            if result.error:
                print(f"에러: {result.error}")

            # genre_results 확인
            print(f"\n=== genre_results (각 장르 1위) ===")
            for key, rankings in agent.genre_results.items():
                label = agent.GENRE_RANKINGS.get(key, {}).get('name', key)
                if rankings:
                    print(f"  [{label}] {len(rankings)}개 → 1위: {rankings[0]['title'][:50]}")
                else:
                    print(f"  [{label}] 0개")

        finally:
            await browser.close()

asyncio.run(main())
