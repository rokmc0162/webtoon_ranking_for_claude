#!/bin/bash
# 웹툰 랭킹 크롤러 실행 스크립트
# launchd에서 호출됨

# 디버그: 스크립트 시작 확인
echo "[$(date '+%Y-%m-%d %H:%M:%S')] run_crawler.sh 시작" >> /tmp/crawler_debug.log

export PATH="/Users/macmini/.pyenv/versions/3.12.11/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export LANG=ko_KR.UTF-8
export HOME="/Users/macmini"
export PYENV_ROOT="/Users/macmini/.pyenv"

# SSD 마운트 대기
SSD_MOUNT="/Volumes/SSD_MacMini"
WAIT_LOG="/tmp/webtoon_ssd_wait.log"
if [ ! -d "${SSD_MOUNT}" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SSD 마운트 대기 중" >> /tmp/crawler_debug.log
    WAITED=0
    while [ ! -d "${SSD_MOUNT}" ] && [ ${WAITED} -lt 300 ]; do
        sleep 10
        WAITED=$((WAITED + 10))
    done
    if [ ! -d "${SSD_MOUNT}" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] SSD 마운트 실패" >> /tmp/crawler_debug.log
        exit 0
    fi
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] SSD OK, 프로젝트 진입" >> /tmp/crawler_debug.log

PROJECT_DIR="/Volumes/SSD_MacMini/WEBTOON Ranking"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/crawler_$(date +%Y-%m-%d).log"

mkdir -p "${LOG_DIR}"

cd "${PROJECT_DIR}" || { echo "[$(date)] cd 실패" >> /tmp/crawler_debug.log; exit 0; }

set -a
source .env 2>/dev/null || true
set +a

git pull origin main --quiet 2>/dev/null || true

echo "" >> "${LOG_FILE}"
echo "========================================" >> "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 크롤러 실행 시작" >> "${LOG_FILE}"
echo "========================================" >> "${LOG_FILE}"

# 핵심: 랭킹 크롤링 (매회 실행, ~30분)
python3 crawler/main.py >> "${LOG_FILE}" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 랭킹 크롤링 완료 (exit: $?)" >> "${LOG_FILE}"

# 부가 작업: 21시 실행분에서만 수행 (리뷰/외부 수집은 하루 1회로 충분)
HOUR=$(date +%H)
if [ "$HOUR" -ge 20 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 21시 실행 — 부가 수집 시작" >> "${LOG_FILE}"

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 외부 데이터 수집 시작..." >> "${LOG_FILE}"
    python3 crawler/main_external.py --max-works 200 >> "${LOG_FILE}" 2>&1
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 외부 데이터 수집 완료" >> "${LOG_FILE}"

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Asura Scans 크롤링 시작..." >> "${LOG_FILE}"
    python3 crawler/main_asura.py --phase rankings >> "${LOG_FILE}" 2>&1
    python3 crawler/main_asura.py --phase series >> "${LOG_FILE}" 2>&1
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Asura Scans 크롤링 완료" >> "${LOG_FILE}"

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 리뷰 수집 시작..." >> "${LOG_FILE}"
    python3 crawler/main_reviews.py >> "${LOG_FILE}" 2>&1
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 리뷰 수집 완료" >> "${LOG_FILE}"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${HOUR}시 실행 — 랭킹만 수집 (부가 수집은 21시에)" >> "${LOG_FILE}"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 모든 크롤링 완료" >> "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] run_crawler.sh 완료" >> /tmp/crawler_debug.log

find "${LOG_DIR}" -name "crawler_*.log" -mtime +30 -delete 2>/dev/null
exit 0
