#!/bin/bash
# 상세 메타데이터 배치 수집 (백그라운드용)
# 200개씩 반복하여 모든 미수집 작품 커버

export PATH="/usr/local/bin:/usr/bin:/bin:/Users/kimyang-il/Library/Python/3.9/bin:$PATH"
export LANG=ko_KR.UTF-8

PROJECT_DIR="/Users/kimyang-il/CLAUDE/webtoon_ranking_for_claude"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/detail_batch_$(date +%Y-%m-%d).log"

mkdir -p "${LOG_DIR}"
cd "${PROJECT_DIR}"
set -a; source .env 2>/dev/null; set +a

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"; }

log "상세 메타데이터 배치 수집 시작"

# 슬립 방지
caffeinate -s -w $$ &
CAF_PID=$!

ROUND=1
MAX_ROUNDS=60
BATCH=200

while [ $ROUND -le $MAX_ROUNDS ]; do
    REMAINING=$(/usr/bin/python3 -c "
from crawler.db import get_works_needing_detail
print(len(get_works_needing_detail(1)))
" 2>/dev/null || echo "0")

    if [ "$REMAINING" = "0" ]; then
        log "완료 - 모든 작품 상세 수집됨"
        break
    fi

    log "라운드 ${ROUND}/${MAX_ROUNDS} (남은 작품 약 ${REMAINING}+개)"
    /usr/bin/python3 -c "
import asyncio
from playwright.async_api import async_playwright
from crawler.detail_scraper import DetailScraper

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        scraper = DetailScraper(max_works=${BATCH}, delay_seconds=2.0)
        await scraper.run(browser)
        await browser.close()

asyncio.run(run())
" >> "${LOG_FILE}" 2>&1 || log "  ⚠️ 라운드 ${ROUND} 일부 실패"

    ROUND=$((ROUND + 1))
    sleep 5
done

log "배치 수집 종료 (총 ${ROUND} 라운드)"
kill $CAF_PID 2>/dev/null || true
