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

# 실행 시작 로그
echo "" >> "${LOG_FILE}"
echo "========================================" >> "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 크롤러 실행 시작" >> "${LOG_FILE}"
echo "========================================" >> "${LOG_FILE}"

# 크롤러 실행
cd "${PROJECT_DIR}"
/usr/bin/python3 crawler/main.py >> "${LOG_FILE}" 2>&1
EXIT_CODE=$?

# 실행 결과 로그
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 크롤러 종료 (exit code: ${EXIT_CODE})" >> "${LOG_FILE}"
echo "" >> "${LOG_FILE}"

# 30일 이상 된 로그 파일 삭제
find "${LOG_DIR}" -name "crawler_*.log" -mtime +30 -delete 2>/dev/null

exit ${EXIT_CODE}
