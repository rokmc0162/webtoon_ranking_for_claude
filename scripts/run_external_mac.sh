#!/bin/bash
# 외부 데이터 수집 (macOS cron용)
# cron 예시:
#   0 3 * * 0  ~/webtoon_ranking/scripts/run_external_mac.sh --anilist --mal
#   0 4 * * *  ~/webtoon_ranking/scripts/run_external_mac.sh --youtube

cd "$HOME/webtoon_ranking"
git pull origin main --quiet 2>/dev/null
source venv/bin/activate
export $(cat .env | xargs)

mkdir -p logs
python3 crawler/main_external.py "$@" >> "logs/external_$(date +%Y-%m-%d).log" 2>&1
