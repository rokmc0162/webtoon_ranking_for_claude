"""
Asura Scans 크롤러 - 별도 실행 스크립트

해적판 사이트이므로 기존 일본 플랫폼 크롤링(main.py)과 분리 실행.
도메인 변경/폐쇄 시 기존 크롤러에 영향 없음.

실행 방법:
    python3 crawler/main_asura.py                     # 전체 (랭킹+시리즈+상세+댓글)
    python3 crawler/main_asura.py --phase rankings     # 랭킹만 (빠름, ~30초)
    python3 crawler/main_asura.py --phase series        # 시리즈 목록만 (~5분)
    python3 crawler/main_asura.py --phase details       # 상세+댓글 (~30분+)
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / '.env')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('crawler.asura')


async def run(phases: list):
    """Asura 크롤링 실행"""
    from playwright.async_api import async_playwright
    from crawler.agents.asura_agent import AsuraAgent
    from crawler.db import init_db

    # DB 연결 확인
    init_db()

    date = datetime.now().strftime('%Y-%m-%d')
    logger.info("=" * 60)
    logger.info(f"🏴‍☠️ Asura Scans 크롤링 시작")
    logger.info(f"📅 날짜: {date}")
    logger.info(f"📋 Phases: {', '.join(phases)}")
    logger.info("=" * 60)

    agent = AsuraAgent()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        try:
            summary = await agent.execute(browser, phases=phases)

            logger.info("")
            logger.info("=" * 60)
            logger.info("📊 크롤링 결과:")
            for key, val in summary.items():
                logger.info(f"   {key}: {val}")
            logger.info("=" * 60)

            # DB 저장
            logger.info("💾 데이터 저장 중...")
            await agent.save_all(date)

            logger.info("")
            logger.info("✅ Asura Scans 크롤링 완료!")

        finally:
            await browser.close()


def main():
    parser = argparse.ArgumentParser(
        description='Asura Scans 크롤러'
    )
    parser.add_argument(
        '--phase', '-p',
        choices=['rankings', 'series', 'details', 'comments', 'all'],
        default='all',
        help='실행할 페이즈 (default: all)'
    )
    args = parser.parse_args()

    if args.phase == 'all':
        phases = ['rankings', 'series', 'details', 'comments']
    elif args.phase == 'details':
        # 상세 수집 시 시리즈 목록도 필요
        phases = ['series', 'details', 'comments']
    else:
        phases = [args.phase]

    try:
        asyncio.run(run(phases))
    except KeyboardInterrupt:
        logger.info("\n⚠️ 사용자가 중단했습니다")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ 크롤링 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
