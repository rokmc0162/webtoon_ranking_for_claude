#!/usr/bin/env python3
"""
Telegram Claude 챗봇 - @nabiman_bot

텔레그램으로 메시지를 보내면 Claude가 답변합니다.
맥북에서 백그라운드 서비스로 실행됩니다.

실행: python3 scripts/telegram_bot.py
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import logging
from pathlib import Path
from datetime import datetime

# 프로젝트 루트
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))
os.chdir(PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(PROJECT_DIR / '.env')
load_dotenv(PROJECT_DIR / 'dashboard-next' / '.env.local', override=True)

import anthropic

# ─── 설정 ──────────────────────────────────────────────────

TELEGRAM_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1024
SYSTEM_PROMPT = (
    "You are a helpful assistant connected via Telegram. "
    "Keep responses concise and mobile-friendly (short paragraphs). "
    "The user is a Korean developer working on a Japanese webtoon ranking project. "
    "Respond in the same language the user writes in."
)

# 대화 히스토리 (메모리 내, 최근 20개)
MAX_HISTORY = 20
conversation_history = []

# 로깅
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_DIR / 'logs' / 'telegram_bot.log'),
    ]
)
log = logging.getLogger('telegram_bot')


# ─── Telegram API ──────────────────────────────────────────

def tg_request(method: str, data: dict = None) -> dict:
    """Telegram Bot API 호출"""
    url = f"{TELEGRAM_API}/{method}"
    if data:
        payload = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    else:
        req = urllib.request.Request(url)

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def send_message(chat_id: str, text: str):
    """텔레그램으로 메시지 전송 (긴 메시지는 분할)"""
    # 텔레그램 메시지 최대 4096자
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        tg_request("sendMessage", {
            "chat_id": chat_id,
            "text": chunk,
        })


def get_updates(offset: int = None) -> list:
    """새 메시지 가져오기 (long polling)"""
    params = {"timeout": 30, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    try:
        result = tg_request("getUpdates", params)
        return result.get("result", [])
    except Exception:
        return []


# ─── Claude API ────────────────────────────────────────────

client = anthropic.Anthropic()


def ask_claude(user_message: str) -> str:
    """Claude에게 질문하고 응답 받기"""
    conversation_history.append({
        "role": "user",
        "content": user_message,
    })

    # 히스토리 제한
    if len(conversation_history) > MAX_HISTORY:
        conversation_history[:] = conversation_history[-MAX_HISTORY:]

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=conversation_history,
        )
        reply = response.content[0].text

        conversation_history.append({
            "role": "assistant",
            "content": reply,
        })
        return reply

    except Exception as e:
        log.error(f"Claude API 오류: {e}")
        return f"⚠️ Claude API 오류: {str(e)[:200]}"


# ─── 메인 루프 ─────────────────────────────────────────────

def main():
    """Long polling으로 메시지 수신 및 응답"""
    # logs 디렉토리 생성
    (PROJECT_DIR / 'logs').mkdir(exist_ok=True)

    log.info("🤖 Telegram Bot 시작 (@nabiman_bot)")
    log.info(f"   모델: {CLAUDE_MODEL}")
    log.info(f"   Chat ID: {CHAT_ID}")

    offset = None

    while True:
        try:
            updates = get_updates(offset)

            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "")

                if not text or chat_id != CHAT_ID:
                    continue

                user_name = msg.get("from", {}).get("first_name", "User")
                log.info(f"📩 {user_name}: {text[:100]}")

                # 특수 명령어
                if text.strip() == "/clear":
                    conversation_history.clear()
                    send_message(chat_id, "🗑 대화 히스토리를 초기화했습니다.")
                    log.info("히스토리 초기화")
                    continue

                if text.strip() == "/status":
                    status = (
                        f"🤖 nabiman_bot 상태\n"
                        f"모델: {CLAUDE_MODEL}\n"
                        f"대화 히스토리: {len(conversation_history)}개\n"
                        f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    send_message(chat_id, status)
                    continue

                # Claude에게 질문
                reply = ask_claude(text)
                send_message(chat_id, reply)
                log.info(f"💬 응답: {reply[:100]}")

        except KeyboardInterrupt:
            log.info("봇 종료")
            break
        except Exception as e:
            log.error(f"오류: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
