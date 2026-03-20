#!/usr/bin/env python3
"""
LINE Manga description 재수집 스크립트
- works 테이블에서 linemanga 플랫폼 중 description이 없는 작품을 조회
- DetailScraper._scrape_linemanga 메서드로 상세 메타 재수집
- save_work_detail로 DB 저장
- 2초 딜레이, 배치 처리, 10개마다 진행 상황 출력
"""

import asyncio
import logging
import sys
from pathlib import Path

# 프로젝트 루트 설정
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / '.env')

import psycopg2
from crawler.db import get_db_connection, save_work_detail
from crawler.detail_scraper import DetailScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(project_root / 'scripts' / 'rescrape_linemanga_desc.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

DELAY_SECONDS = 2.0
BATCH_SIZE = 50  # Playwright context refresh interval


def get_linemanga_works_missing_desc():
    """description이 없는 linemanga 작품 목록 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT title, url
        FROM works
        WHERE platform = 'linemanga'
          AND (description IS NULL OR description = '')
          AND url IS NOT NULL
          AND url != ''
        ORDER BY title
    """)
    rows = cursor.fetchall()
    conn.close()
    return [{'title': r[0], 'url': r[1]} for r in rows]


async def rescrape_linemanga():
    from playwright.async_api import async_playwright

    # 1) 대상 작품 조회
    works = get_linemanga_works_missing_desc()
    total = len(works)
    logger.info(f"LINE Manga description 미수집 작품: {total}개")

    if total == 0:
        logger.info("재수집 대상 없음. 종료.")
        return

    scraper = DetailScraper()
    success = 0
    failed = 0
    skipped = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # 배치 단위로 컨텍스트 갱신 (메모리 누수 방지)
        for batch_start in range(0, total, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total)
            batch = works[batch_start:batch_end]
            logger.info(f"--- 배치 {batch_start+1}~{batch_end} / {total} ---")

            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
            )
            page = await context.new_page()

            for i, work in enumerate(batch, batch_start + 1):
                title = work['title']
                url = work['url']

                try:
                    detail = await scraper._scrape_linemanga(page, url)

                    if detail and detail.get('description'):
                        save_work_detail('linemanga', title, detail)
                        success += 1
                        desc_preview = detail['description'][:60].replace('\n', ' ')
                        if i <= 5 or i % 10 == 0:
                            logger.info(f"  [{i}/{total}] OK: {title[:40]} => {desc_preview}...")
                    elif detail:
                        # detail은 있지만 description이 없음 - 다른 필드라도 저장
                        save_work_detail('linemanga', title, detail)
                        skipped += 1
                        if i <= 5 or i % 10 == 0:
                            logger.info(f"  [{i}/{total}] PARTIAL (no desc): {title[:40]}")
                    else:
                        failed += 1
                        if i <= 5 or i % 10 == 0:
                            logger.info(f"  [{i}/{total}] EMPTY: {title[:40]}")

                except Exception as e:
                    failed += 1
                    logger.warning(f"  [{i}/{total}] FAIL: {title[:40]} - {e}")

                # 진행 상황 (10개마다)
                if i % 10 == 0:
                    logger.info(f"  === 진행: {i}/{total} (성공:{success}, 부분:{skipped}, 실패:{failed}) ===")

                # 딜레이
                if i < total:
                    await asyncio.sleep(DELAY_SECONDS)

            await page.close()
            await context.close()
            logger.info(f"--- 배치 완료. 누적: 성공:{success}, 부분:{skipped}, 실패:{failed} ---")

        await browser.close()

    logger.info("=" * 60)
    logger.info(f"LINE Manga description 재수집 완료")
    logger.info(f"  총 대상: {total}")
    logger.info(f"  description 수집 성공: {success}")
    logger.info(f"  description 없음 (부분 저장): {skipped}")
    logger.info(f"  실패: {failed}")
    logger.info("=" * 60)


if __name__ == '__main__':
    asyncio.run(rescrape_linemanga())
