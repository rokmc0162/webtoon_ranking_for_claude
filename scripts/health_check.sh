#!/bin/bash
# 크롤러 헬스체크 스크립트
# 오늘 데이터가 수집되었는지 확인하고, 실패 시 알림

PROJECT_DIR="/Users/kimyang-il/CLAUDE/webtoon_ranking_for_claude"
DB_PATH="${PROJECT_DIR}/data/rankings.db"
LOG_DIR="${PROJECT_DIR}/logs"
HEALTH_LOG="${LOG_DIR}/health_$(date +%Y-%m-%d).log"
TODAY=$(date +%Y-%m-%d)

mkdir -p "${LOG_DIR}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 헬스체크 시작" >> "${HEALTH_LOG}"

# 1. DB 파일 존재 확인
if [ ! -f "${DB_PATH}" ]; then
    echo "  FAIL: DB 파일 없음 (${DB_PATH})" >> "${HEALTH_LOG}"
    osascript -e 'display notification "DB 파일이 없습니다!" with title "웹툰 크롤러 경고"' 2>/dev/null
    exit 1
fi

# 2. 오늘 날짜 데이터 확인
COUNT=$(sqlite3 "${DB_PATH}" "SELECT COUNT(*) FROM rankings WHERE date='${TODAY}';" 2>/dev/null)

if [ -z "${COUNT}" ] || [ "${COUNT}" -eq 0 ]; then
    echo "  FAIL: 오늘(${TODAY}) 수집된 데이터 없음" >> "${HEALTH_LOG}"
    osascript -e "display notification \"오늘(${TODAY}) 데이터가 없습니다!\" with title \"웹툰 크롤러 경고\"" 2>/dev/null
    exit 1
fi

# 3. 플랫폼별 수집 현황
echo "  오늘(${TODAY}) 수집 현황:" >> "${HEALTH_LOG}"

for PLATFORM in piccoma mechacomic cmoa linemanga; do
    P_COUNT=$(sqlite3 "${DB_PATH}" "SELECT COUNT(*) FROM rankings WHERE date='${TODAY}' AND platform='${PLATFORM}';" 2>/dev/null)
    if [ "${P_COUNT}" -gt 0 ]; then
        echo "    OK: ${PLATFORM}: ${P_COUNT}개" >> "${HEALTH_LOG}"
    else
        echo "    WARN: ${PLATFORM}: 0개 (수집 실패)" >> "${HEALTH_LOG}"
    fi
done

echo "  총 ${COUNT}개 작품 수집 확인" >> "${HEALTH_LOG}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 헬스체크 완료" >> "${HEALTH_LOG}"

# macOS 알림
osascript -e "display notification \"오늘 ${COUNT}개 작품 수집 완료\" with title \"웹툰 크롤러 정상\"" 2>/dev/null

exit 0
