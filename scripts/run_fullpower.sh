#!/bin/bash
# 풀파워 크롤링 스크립트
# 랭킹 크롤링 (12개 플랫폼) + 외부 데이터 수집 (9개 소스) + 리뷰 수집

set -e

# 환경 설정
export PATH="/usr/local/bin:/usr/bin:/bin:/Users/kimyang-il/Library/Python/3.9/bin:$PATH"
export LANG=ko_KR.UTF-8

PROJECT_DIR="/Users/kimyang-il/CLAUDE/webtoon_ranking_for_claude"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/fullpower_$(date +%Y-%m-%d_%H%M).log"

mkdir -p "${LOG_DIR}"
cd "${PROJECT_DIR}"

# .env 로딩
set -a
source .env
set +a

echo "========================================" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 풀파워 크롤링 시작" | tee -a "${LOG_FILE}"
echo "========================================" | tee -a "${LOG_FILE}"

# 1. git pull (최신 코드 반영)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Step 1: git pull..." | tee -a "${LOG_FILE}"
git pull origin main --quiet 2>/dev/null || true

# 2. 메인 크롤링 (12개 플랫폼 랭킹 + 상세 메타데이터)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Step 2: 12개 플랫폼 랭킹 크롤링 시작..." | tee -a "${LOG_FILE}"
/usr/bin/python3 crawler/main.py 2>&1 | tee -a "${LOG_FILE}"
CRAWL_EXIT=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 랭킹 크롤링 완료 (exit: ${CRAWL_EXIT})" | tee -a "${LOG_FILE}"

# 3. 외부 데이터 수집 (전체 9개 소스, 최대 500개 작품)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Step 3: 외부 데이터 수집 시작 (9개 소스)..." | tee -a "${LOG_FILE}"
/usr/bin/python3 crawler/main_external.py --all --max-works 500 2>&1 | tee -a "${LOG_FILE}"
EXT_EXIT=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 외부 데이터 수집 완료 (exit: ${EXT_EXIT})" | tee -a "${LOG_FILE}"

# 4. 리뷰 수집
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Step 4: 리뷰 수집 시작..." | tee -a "${LOG_FILE}"
/usr/bin/python3 crawler/main_reviews.py 2>&1 | tee -a "${LOG_FILE}"
REV_EXIT=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 리뷰 수집 완료 (exit: ${REV_EXIT})" | tee -a "${LOG_FILE}"

echo "========================================" | tee -a "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 풀파워 크롤링 전체 완료!" | tee -a "${LOG_FILE}"
echo "  랭킹: exit ${CRAWL_EXIT}, 외부: exit ${EXT_EXIT}, 리뷰: exit ${REV_EXIT}" | tee -a "${LOG_FILE}"
echo "========================================" | tee -a "${LOG_FILE}"
