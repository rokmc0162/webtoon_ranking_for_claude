#!/bin/bash
# 웹툰 랭킹 크롤러 실행 스크립트
# launchd에서 호출됨

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export LANG=ko_KR.UTF-8
export HOME="/Users/macmini"

# SSD 마운트 대기 (재부팅 시 launchd가 SSD 마운트 전에 실행되는 경우 대비)
SSD_MOUNT="/Volumes/SSD_MacMini"
WAIT_LOG="/tmp/webtoon_ssd_wait.log"
if [ ! -d "${SSD_MOUNT}" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SSD 마운트 대기 중: ${SSD_MOUNT}" >> "${WAIT_LOG}"
    WAITED=0
    while [ ! -d "${SSD_MOUNT}" ] && [ ${WAITED} -lt 300 ]; do
        sleep 10
        WAITED=$((WAITED + 10))
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 대기 중... (${WAITED}초 경과)" >> "${WAIT_LOG}"
    done
    if [ ! -d "${SSD_MOUNT}" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: SSD가 300초 내에 마운트되지 않음. 크롤러 종료." >> "${WAIT_LOG}"
        exit 78
    fi
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SSD 마운트 확인 완료 (${WAITED}초 대기)" >> "${WAIT_LOG}"
fi

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
