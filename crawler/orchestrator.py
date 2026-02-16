"""
Crawler orchestrator for parallel agent execution.

Manages the lifecycle and coordination of all platform crawler agents.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List
from playwright.async_api import async_playwright, Browser

from crawler.agents.base_agent import AgentResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('crawler.orchestrator')


class CrawlerOrchestrator:
    """
    Orchestrates parallel execution of all crawler agents.

    Features:
    - Parallel execution using asyncio.gather()
    - Error isolation (one failure doesn't affect others)
    - Centralized logging and result aggregation
    - Shared browser instance for efficiency
    """

    def __init__(self):
        """Initialize orchestrator."""
        self.date = datetime.now().strftime('%Y-%m-%d')
        self.logger = logger

    async def run_all(self) -> Dict[str, AgentResult]:
        """
        Execute all crawler agents in parallel.

        Returns:
            Dict mapping platform_id to AgentResult
        """
        self.logger.info("=" * 70)
        self.logger.info(f"🚀 일본 웹툰 랭킹 크롤링 시작")
        self.logger.info(f"📅 날짜: {self.date}")
        self.logger.info("=" * 70)

        # Import agents here to avoid circular imports
        from crawler.agents.piccoma_agent import PiccomaAgent
        from crawler.agents.linemanga_agent import LinemangaAgent
        from crawler.agents.mechacomic_agent import MechacomicAgent
        from crawler.agents.cmoa_agent import CmoaAgent

        # Initialize browser
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            try:
                # Create agent instances
                agents = [
                    PiccomaAgent(),
                    LinemangaAgent(),
                    MechacomicAgent(),
                    CmoaAgent()
                ]

                # Execute all agents in parallel
                # return_exceptions=True prevents one failure from canceling others
                self.logger.info("Starting parallel execution of 4 agents...")

                results = await asyncio.gather(
                    *[agent.execute(browser) for agent in agents],
                    return_exceptions=True
                )

                # Process results
                results_dict = {}
                success_count = 0
                fail_count = 0

                for result in results:
                    if isinstance(result, Exception):
                        # Unexpected error (shouldn't happen with proper error handling)
                        self.logger.error(f"Unexpected error: {result}")
                        continue

                    results_dict[result.platform] = result

                    if result.success:
                        success_count += 1
                    else:
                        fail_count += 1

                # Print summary
                self.logger.info("")
                self.logger.info("=" * 70)
                self.logger.info("✅ 크롤링 완료")
                self.logger.info("=" * 70)
                self.logger.info(f"📊 성공: {success_count}/4개 플랫폼")
                self.logger.info(f"❌ 실패: {fail_count}/4개 플랫폼")
                self.logger.info("")

                # Print detailed results
                for platform_id, result in results_dict.items():
                    if result.success:
                        self.logger.info(f"   ✅ {platform_id}: {result.count}개 작품")
                    else:
                        self.logger.info(f"   ❌ {platform_id}: {result.error}")

                # Print summary statistics
                total_items = sum(r.count for r in results_dict.values() if r.success)
                self.logger.info("")
                self.logger.info(f"📚 총 {total_items}개 작품 수집")
                self.logger.info(f"💾 데이터 저장: data/rankings.db")
                self.logger.info(f"📦 백업: data/backup/{self.date}/")
                self.logger.info("=" * 70)

                if fail_count > 0:
                    self.logger.warning(f"⚠️  일부 플랫폼 크롤링 실패 ({success_count}/4)")

                return results_dict

            finally:
                # Always close browser
                await browser.close()
                self.logger.debug("Browser closed")


async def main():
    """Main entry point for orchestrator."""
    orchestrator = CrawlerOrchestrator()
    await orchestrator.run_all()


if __name__ == "__main__":
    asyncio.run(main())
