@echo off
REM 대시보드 실행 스크립트 (Windows)

echo 🚀 일본 웹툰 랭킹 대시보드 실행 중...
echo.

REM 가상환경 활성화 (존재하는 경우)
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM Streamlit 실행
streamlit run dashboard/app.py

pause
