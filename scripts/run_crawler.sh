#!/bin/bash
# 웹툰 랭킹 크롤러 실행 스크립트
# launchd에서 호출됨 - 환경변수 및 로깅 설정

# 환경 설정
export PATH="/usr/local/bin:/usr/bin:/bin:/Users/kimyang-il/Library/Python/3.9/bin:$PATH"
export LANG=ko_KR.UTF-8

# 프로젝트 경로
PROJECT_DIR="/Users/kimyang-il/CLAUDE/webtoon_ranking_for_claude"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/crawler_$(date +%Y-%m-%d).log"

# 로그 디렉토리 생성
mkdir -p "${LOG_DIR}"

# .env 로딩
cd "${PROJECT_DIR}"
set -a
source .env 2>/dev/null || true
set +a

# git pull (최신 코드 반영)
git pull origin main --quiet 2>/dev/null || true

# 실행 시작 로그
echo "" >> "${LOG_FILE}"
echo "========================================" >> "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 크롤러 실행 시작" >> "${LOG_FILE}"
echo "========================================" >> "${LOG_FILE}"

# 1. 메인 크롤링 (12개 플랫폼)
/usr/bin/python3 crawler/main.py >> "${LOG_FILE}" 2>&1
EXIT_CODE=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 랭킹 크롤링 완료 (exit: ${EXIT_CODE})" >> "${LOG_FILE}"

# 2. 외부 데이터 수집 (기본 3개: anilist, mal, youtube)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 외부 데이터 수집 시작..." >> "${LOG_FILE}"
/usr/bin/python3 crawler/main_external.py --max-works 200 >> "${LOG_FILE}" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 외부 데이터 수집 완료" >> "${LOG_FILE}"

# 3. Asura Scans 크롤링 (해적판 - 분리 실행, 실패해도 기존 크롤러에 영향 없음)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Asura Scans 크롤링 시작..." >> "${LOG_FILE}"
/usr/bin/python3 crawler/main_asura.py --phase rankings >> "${LOG_FILE}" 2>&1
/usr/bin/python3 crawler/main_asura.py --phase series >> "${LOG_FILE}" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Asura Scans 크롤링 완료" >> "${LOG_FILE}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 모든 크롤링 완료" >> "${LOG_FILE}"
echo "" >> "${LOG_FILE}"

# 30일 이상 된 로그 파일 삭제
find "${LOG_DIR}" -name "crawler_*.log" -mtime +30 -delete 2>/dev/null

exit ${EXIT_CODE}
