"""4개 플랫폼 100위 수집 테스트"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from playwright.async_api import async_playwright


async def test_comico():
    """코미코 테스트"""
    from crawler.agents.comico_agent import ComicoAgent
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        agent = ComicoAgent()
        agent.GENRE_RANKINGS = {'': {'name': '종합(데일리)', 'code': ''}}
        results = await agent.crawl(browser)
        await browser.close()
        with_thumb = sum(1 for r in results if r.get('thumbnail_url'))
        print(f"\n=== 코미코: {len(results)}개, 썸네일 {with_thumb}개 ===")
        if results:
            print(f"  1위: {results[0]['title']}")
            if len(results) >= 50:
                print(f"  50위: {results[49]['title']}")
            if len(results) >= 100:
                print(f"  100위: {results[99]['title']}")
            print(f"  마지막: {results[-1]['rank']}위 {results[-1]['title']}")
        return len(results)


async def test_lezhin():
    """레진 테스트"""
    from crawler.agents.lezhin_agent import LezhinAgent
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        agent = LezhinAgent()
        agent.GENRE_RANKINGS = {'': {'name': '종합', 'tab': ''}}
        results = await agent.crawl(browser)
        await browser.close()
        with_thumb = sum(1 for r in results if r.get('thumbnail_url'))
        print(f"\n=== 레진: {len(results)}개, 썸네일 {with_thumb}개 ===")
        if results:
            print(f"  1위: {results[0]['title']}")
            if len(results) >= 50:
                print(f"  50위: {results[49]['title']}")
            if len(results) >= 100:
                print(f"  100위: {results[99]['title']}")
            print(f"  마지막: {results[-1]['rank']}위 {results[-1]['title']}")
        return len(results)


async def test_unext():
    """U-NEXT 테스트"""
    from crawler.agents.unext_agent import UnextAgent
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        agent = UnextAgent()
        results = await agent.crawl(browser)
        await browser.close()
        with_thumb = sum(1 for r in results if r.get('thumbnail_url'))
        print(f"\n=== U-NEXT: {len(results)}개, 썸네일 {with_thumb}개 ===")
        if results:
            print(f"  1위: {results[0]['title']}")
            if len(results) >= 50:
                print(f"  50위: {results[49]['title']}")
            if len(results) >= 100:
                print(f"  100위: {results[99]['title']}")
            print(f"  마지막: {results[-1]['rank']}위 {results[-1]['title']}")
        return len(results)


async def main():
    target = sys.argv[1] if len(sys.argv) > 1 else 'all'

    if target in ('comico', 'all'):
        c = await test_comico()
        print(f"코미코: {'✅' if c >= 100 else '❌'} {c}개")

    if target in ('lezhin', 'all'):
        l = await test_lezhin()
        print(f"레진: {'✅' if l >= 100 else '❌'} {l}개")

    if target in ('unext', 'all'):
        u = await test_unext()
        print(f"U-NEXT: {'✅' if u >= 100 else '❌'} {u}개")


asyncio.run(main())
