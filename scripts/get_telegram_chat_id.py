#!/usr/bin/env python3
"""
Telegram Bot의 chat_id를 확인하는 스크립트

사용법:
    1. @BotFather에서 봇을 만들고 토큰을 .env에 저장
    2. 텔레그램에서 봇에게 아무 메시지 보내기
    3. 이 스크립트 실행:
       python3 scripts/get_telegram_chat_id.py
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

# .env 로드
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv('dashboard-next/.env.local', override=True)
except ImportError:
    pass

token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
if not token:
    print("❌ TELEGRAM_BOT_TOKEN이 .env에 없습니다.")
    print()
    print("설정 방법:")
    print("  1. 텔레그램에서 @BotFather 검색")
    print("  2. /newbot 명령어 → 봇 이름/유저네임 입력")
    print("  3. 받은 토큰을 .env에 추가:")
    print("     TELEGRAM_BOT_TOKEN=여기에토큰붙여넣기")
    sys.exit(1)

url = f"https://api.telegram.org/bot{token}/getUpdates"
try:
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())
except Exception as e:
    print(f"❌ API 호출 실패: {e}")
    sys.exit(1)

if not data.get("ok") or not data.get("result"):
    print("❌ 메시지가 없습니다.")
    print()
    print("→ 텔레그램에서 봇에게 아무 메시지를 보낸 후 다시 실행하세요.")
    sys.exit(1)

# 최신 메시지에서 chat_id 추출
msg = data["result"][-1].get("message", {})
chat_id = msg.get("chat", {}).get("id")
chat_name = msg.get("chat", {}).get("first_name", "")

if chat_id:
    print(f"✅ chat_id: {chat_id}  ({chat_name})")
    print()
    print(f".env에 추가하세요:")
    print(f"  TELEGRAM_CHAT_ID={chat_id}")
else:
    print("❌ chat_id를 찾을 수 없습니다. 봇에게 메시지를 보내주세요.")
