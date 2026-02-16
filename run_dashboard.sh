#!/bin/bash
# 대시보드 실행 스크립트

echo "🚀 일본 웹툰 랭킹 대시보드 실행 중..."
echo ""

# 가상환경 활성화 (존재하는 경우)
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Streamlit 실행
streamlit run dashboard/app.py
