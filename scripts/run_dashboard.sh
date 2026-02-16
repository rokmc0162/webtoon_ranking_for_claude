#!/bin/bash
# Streamlit 대시보드 실행 스크립트
# launchd에서 호출됨 - 환경변수 설정 후 Streamlit 서버 실행

# 환경 설정
export PATH="/usr/local/bin:/usr/bin:/bin:/Users/kimyang-il/Library/Python/3.9/bin:$PATH"
export LANG=ko_KR.UTF-8

# 프로젝트 경로
PROJECT_DIR="/Users/kimyang-il/CLAUDE/webtoon_ranking_for_claude"

# 기존 Streamlit 프로세스 종료 (포트 충돌 방지)
lsof -ti:8501 2>/dev/null | xargs kill 2>/dev/null
sleep 1

# Streamlit 실행 (포그라운드 - launchd가 관리)
cd "${PROJECT_DIR}"
exec /usr/bin/python3 -m streamlit run dashboard/app.py \
    --server.port 8501 \
    --server.headless true \
    --server.address 0.0.0.0
