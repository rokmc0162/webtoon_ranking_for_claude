#!/bin/bash
set -e

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 컨테이너 시작..."

# 1. DB 초기화 (테이블 없으면 생성)
cd /app
python3 -c "from crawler.db import init_db; init_db()"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] DB 초기화 완료"

# 2. cron 데몬 시작 (크롤러 스케줄링)
cron
echo "[$(date '+%Y-%m-%d %H:%M:%S')] cron 시작됨 (9/15/21시 크롤링)"

# 3. cloudflared 터널 (백그라운드)
/app/docker/tunnel.sh &
echo "[$(date '+%Y-%m-%d %H:%M:%S')] cloudflared 터널 시작됨"

# 4. Streamlit 대시보드 (포그라운드 — 컨테이너 메인 프로세스)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Streamlit 대시보드 시작..."
exec python3 -m streamlit run dashboard/app.py \
    --server.port 8501 \
    --server.headless true \
    --server.address 0.0.0.0
