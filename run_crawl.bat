@echo off
cd /d "d:\CLAUDE YANGIL\webtoon_ranking_for_claude\webtoon_ranking_for_claude"
call venv\Scripts\activate
python crawler\main.py >> logs\crawler_%date:~0,4%-%date:~5,2%-%date:~8,2%.log 2>&1
