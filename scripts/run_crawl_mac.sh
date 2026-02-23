#!/bin/bash
cd "$HOME/webtoon_ranking"
git pull origin main --quiet 2>/dev/null
source venv/bin/activate
export $(cat .env | xargs)
python3 crawler/main.py >> "$HOME/webtoon_ranking/logs/crawler_$(date +%Y-%m-%d).log" 2>&1
