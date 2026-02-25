#!/bin/bash
# ============================================================
# 야간 전체 수집 스크립트
# 모든 작품의 메타데이터, 리뷰, 외부 데이터 완전 수집
# 클램쉘 모드에서 밤새 돌릴 용도
# ============================================================

set -e

# 환경 설정
export PATH="/usr/local/bin:/usr/bin:/bin:/Users/kimyang-il/Library/Python/3.9/bin:$PATH"
export LANG=ko_KR.UTF-8

PROJECT_DIR="/Users/kimyang-il/CLAUDE/webtoon_ranking_for_claude"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/overnight_$(date +%Y-%m-%d).log"

mkdir -p "${LOG_DIR}"
cd "${PROJECT_DIR}"

# .env 로딩
set -a
source .env 2>/dev/null || true
set +a

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

log "============================================"
log "야간 전체 수집 시작"
log "============================================"

# macOS 슬립 방지 (카페인 - 프로세스 종료 시 자동 해제)
caffeinate -s -w $$ &
CAFFEINATE_PID=$!
log "슬립 방지 활성화 (caffeinate PID: ${CAFFEINATE_PID})"

# ============================================================
# Phase 1: 메인 랭킹 크롤링 (일일 작업)
# ============================================================
log ""
log "=== Phase 1: 메인 랭킹 크롤링 ==="
/usr/bin/python3 crawler/main.py >> "${LOG_FILE}" 2>&1 || log "⚠️ 메인 크롤링 일부 실패 (계속 진행)"
log "Phase 1 완료"

# ============================================================
# Phase 2: Asura 크롤링
# ============================================================
log ""
log "=== Phase 2: Asura 크롤링 ==="
/usr/bin/python3 crawler/main_asura.py --phase rankings >> "${LOG_FILE}" 2>&1 || true
/usr/bin/python3 crawler/main_asura.py --phase series >> "${LOG_FILE}" 2>&1 || true
log "Phase 2 완료"

# ============================================================
# Phase 3: 상세 메타데이터 전체 수집 (6000+ 작품)
# 50개씩 반복, 플랫폼별로 분산하여 전체 커버
# ============================================================
log ""
log "=== Phase 3: 상세 메타데이터 전체 수집 ==="

# detail_scraper를 반복 호출 (한번에 200개씩, 최대 40라운드 = 8000개)
ROUND=1
MAX_ROUNDS=40
BATCH_SIZE=200

while [ $ROUND -le $MAX_ROUNDS ]; do
    # 남은 작품 수 체크
    REMAINING=$(/usr/bin/python3 -c "
from crawler.db import get_works_needing_detail
works = get_works_needing_detail(1)
print(len(works))
" 2>/dev/null || echo "0")

    if [ "$REMAINING" = "0" ]; then
        log "상세 수집 완료 - 더 이상 대상 없음"
        break
    fi

    log "상세 수집 라운드 ${ROUND}/${MAX_ROUNDS} (배치: ${BATCH_SIZE}개)"
    /usr/bin/python3 -c "
import asyncio
from playwright.async_api import async_playwright
from crawler.detail_scraper import DetailScraper

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        scraper = DetailScraper(max_works=${BATCH_SIZE}, delay_seconds=2.0)
        await scraper.run(browser)
        await browser.close()

asyncio.run(run())
" >> "${LOG_FILE}" 2>&1 || log "  ⚠️ 라운드 ${ROUND} 일부 실패"

    ROUND=$((ROUND + 1))
    # 라운드 간 10초 대기 (서버 부하 방지)
    sleep 10
done
log "Phase 3 완료 (${ROUND} 라운드)"

# ============================================================
# Phase 4: 리뷰 전체 수집 (모든 플랫폼)
# ============================================================
log ""
log "=== Phase 4: 리뷰 전체 수집 ==="

# 전체 작품 리뷰 (max-works 0 = 무제한)
/usr/bin/python3 crawler/main_reviews.py --max-works 0 >> "${LOG_FILE}" 2>&1 || log "⚠️ 리뷰 수집 일부 실패"
log "Phase 4 완료"

# ============================================================
# Phase 5: Asura 상세 + 코멘트 수집
# ============================================================
log ""
log "=== Phase 5: Asura 상세/코멘트 수집 ==="
/usr/bin/python3 crawler/main_asura.py --phase details >> "${LOG_FILE}" 2>&1 || true
/usr/bin/python3 crawler/main_asura.py --phase comments >> "${LOG_FILE}" 2>&1 || true
log "Phase 5 완료"

# ============================================================
# Phase 6: 외부 데이터 수집 (AniList + MAL + YouTube)
# ============================================================
log ""
log "=== Phase 6: 외부 데이터 수집 ==="

# 기본 3개 소스로 전체 작품 수집
/usr/bin/python3 crawler/main_external.py --anilist --mal --youtube --max-works 0 >> "${LOG_FILE}" 2>&1 || log "⚠️ 외부 데이터 수집 일부 실패"
log "Phase 6 완료"

# ============================================================
# Phase 7: 결과 요약
# ============================================================
log ""
log "=== 결과 요약 ==="

/usr/bin/python3 -c "
import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.environ['SUPABASE_DB_URL'])
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM works')
print(f'전체 works: {cur.fetchone()[0]:,}개')

cur.execute('SELECT COUNT(*) FROM works WHERE detail_scraped_at IS NOT NULL')
print(f'상세 수집 완료: {cur.fetchone()[0]:,}개')

cur.execute('SELECT COUNT(*) FROM works WHERE detail_scraped_at IS NULL')
print(f'상세 미수집: {cur.fetchone()[0]:,}개')

cur.execute('SELECT platform, COUNT(*) FROM reviews GROUP BY platform ORDER BY COUNT(*) DESC')
print()
print('리뷰 현황:')
total = 0
for p, c in cur.fetchall():
    print(f'  {p}: {c:,}건')
    total += c
print(f'  전체: {total:,}건')

cur.execute('SELECT COUNT(DISTINCT title) FROM external_data')
ext = cur.fetchone()[0]
print(f'\n외부 데이터: {ext}개 작품')

conn.close()
" >> "${LOG_FILE}" 2>&1

log ""
log "============================================"
log "야간 전체 수집 완료!"
log "============================================"

# caffeinate 종료
kill $CAFFEINATE_PID 2>/dev/null || true
