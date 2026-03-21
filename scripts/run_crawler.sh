#!/bin/bash
# 웹툰 랭킹 크롤러 실행 스크립트
# launchd에서 호출됨

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export LANG=ko_KR.UTF-8
export HOME="/Users/macmini"

PROJECT_DIR="/Volumes/SSD_MacMini/WEBTOON Ranking"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/crawler_$(date +%Y-%m-%d).log"

mkdir -p "${LOG_DIR}"

cd "${PROJECT_DIR}"
set -a
source .env 2>/dev/null || true
set +a

git pull origin main --quiet 2>/dev/null || true

echo "" >> "${LOG_FILE}"
echo "========================================" >> "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 크롤러 실행 시작" >> "${LOG_FILE}"
echo "========================================" >> "${LOG_FILE}"

/usr/bin/python3 crawler/main.py >> "${LOG_FILE}" 2>&1
EXIT_CODE=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 랭킹 크롤링 완료 (exit: ${EXIT_CODE})" >> "${LOG_FILE}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 외부 데이터 수집 시작..." >> "${LOG_FILE}"
/usr/bin/python3 crawler/main_external.py --max-works 200 >> "${LOG_FILE}" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 외부 데이터 수집 완료" >> "${LOG_FILE}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Asura Scans 크롤링 시작..." >> "${LOG_FILE}"
/usr/bin/python3 crawler/main_asura.py --phase rankings >> "${LOG_FILE}" 2>&1
/usr/bin/python3 crawler/main_asura.py --phase series >> "${LOG_FILE}" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Asura Scans 크롤링 완료" >> "${LOG_FILE}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 리뷰 수집 시작..." >> "${LOG_FILE}"
/usr/bin/python3 crawler/main_reviews.py >> "${LOG_FILE}" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 리뷰 수집 완료" >> "${LOG_FILE}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 모든 크롤링 완료" >> "${LOG_FILE}"

find "${LOG_DIR}" -name "crawler_*.log" -mtime +30 -delete 2>/dev/null
exit ${EXIT_CODE}
