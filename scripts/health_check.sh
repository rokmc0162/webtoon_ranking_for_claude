#!/bin/bash
PROJECT_DIR="/Volumes/SSD_MacMini/WEBTOON Ranking"
LOG_DIR="${PROJECT_DIR}/logs"
HEALTH_LOG="${LOG_DIR}/health_$(date +%Y-%m-%d).log"
TODAY=$(date +%Y-%m-%d)

mkdir -p "${LOG_DIR}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 헬스체크 시작" >> "${HEALTH_LOG}"

cd "${PROJECT_DIR}"
set -a
source .env 2>/dev/null || true
set +a

# Supabase DB 확인 (psql)
COUNT=$(/usr/bin/python3 -c "
import os, psycopg2
conn = psycopg2.connect(os.environ['SUPABASE_DB_URL'])
cur = conn.cursor()
cur.execute(\"SELECT COUNT(*) FROM rankings WHERE date='${TODAY}'\")
print(cur.fetchone()[0])
conn.close()
" 2>/dev/null || echo "0")

if [ "${COUNT}" -eq 0 ] 2>/dev/null; then
    echo "  FAIL: 오늘(${TODAY}) 수집된 데이터 없음" >> "${HEALTH_LOG}"
    osascript -e "display notification \"오늘(${TODAY}) 데이터가 없습니다!\" with title \"웹툰 크롤러 경고\"" 2>/dev/null
else
    echo "  OK: 오늘(${TODAY}) ${COUNT}개 수집" >> "${HEALTH_LOG}"
    osascript -e "display notification \"오늘 ${COUNT}개 수집 완료\" with title \"웹툰 크롤러 정상\"" 2>/dev/null
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 헬스체크 완료" >> "${HEALTH_LOG}"
