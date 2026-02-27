"""
크롤링 알림 모듈

1순위: Telegram Bot (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)
2순위: Slack Webhook (SLACK_WEBHOOK_URL, 선택)
부가: macOS 알림 (항상)

Telegram 설정법:
    1. @BotFather에게 /newbot → 봇 토큰 받기
    2. 생성된 봇에게 아무 메시지 보내기
    3. python3 scripts/get_telegram_chat_id.py 실행 → chat_id 확인
    4. .env에 추가:
       TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
       TELEGRAM_CHAT_ID=987654321
"""

import json
import os
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, Optional


# ─── Telegram ──────────────────────────────────────────────

def send_telegram(message: str) -> bool:
    """Telegram Bot API로 메시지 전송"""
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }).encode('utf-8')
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"⚠️  Telegram 전송 실패: {e}")
        return False


# ─── macOS 알림 ────────────────────────────────────────────

def send_macos_notification(title: str, subtitle: str, body: str) -> bool:
    """macOS 알림센터로 알림 전송"""
    def esc(s):
        return s.replace('\\', '\\\\').replace('"', '\\"')
    script = (
        f'display notification "{esc(body)}" '
        f'with title "{esc(title)}" '
        f'subtitle "{esc(subtitle)}" '
        f'sound name "Glass"'
    )
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


# ─── Slack (선택) ──────────────────────────────────────────

def send_slack(message: str) -> bool:
    """Slack Incoming Webhook 전송 (선택사항)"""
    url = os.environ.get('SLACK_WEBHOOK_URL', '')
    if not url:
        return False
    payload = json.dumps({"text": message}).encode('utf-8')
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


# ─── 메인 알림 함수 ────────────────────────────────────────

def notify_crawl_complete(results: Dict, elapsed_seconds: float = 0) -> bool:
    """크롤링 완료 알림 전송 (Telegram + macOS + Slack)"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    success_platforms = []
    failed_platforms = []
    total_count = 0

    for platform, result in sorted(results.items()):
        if result.success:
            success_platforms.append((platform, result.count))
            total_count += result.count
        else:
            err = (result.error or "알 수 없음")[:60]
            failed_platforms.append((platform, err))

    # 시간 포맷
    if elapsed_seconds > 0:
        mins, secs = divmod(int(elapsed_seconds), 60)
        time_str = f"{mins}분 {secs}초" if mins else f"{secs}초"
    else:
        time_str = "-"

    n_success = len(success_platforms)
    n_total = len(results)

    # ── Telegram 메시지 (HTML) ──
    if failed_platforms:
        icon = "⚠️"
    else:
        icon = "✅"

    tg_lines = [
        f"{icon} <b>크롤링 완료</b> ({now})",
        f"📊 수집: {total_count}개 | ⏱ {time_str} | {n_success}/{n_total} 성공",
        "",
    ]
    for p, c in success_platforms:
        tg_lines.append(f"  • {p}: {c}개")
    if failed_platforms:
        tg_lines.append("")
        for p, err in failed_platforms:
            tg_lines.append(f"  ❌ {p}: {err}")

    tg_msg = "\n".join(tg_lines)
    sent = send_telegram(tg_msg)
    if sent:
        print("📱 Telegram 알림 전송 완료")
    elif os.environ.get('TELEGRAM_BOT_TOKEN'):
        print("⚠️  Telegram 알림 전송 실패")

    # ── macOS 알림 (항상) ──
    subtitle = f"📊 {total_count}개 | ⏱ {time_str}"
    body_parts = [f"{p}: {c}개" for p, c in success_platforms[:6]]
    if failed_platforms:
        body_parts.append(f"❌실패: {', '.join(p for p, _ in failed_platforms)}")
    send_macos_notification(f"{icon} 크롤링 완료", subtitle, " | ".join(body_parts))

    # ── Slack (선택) ──
    if os.environ.get('SLACK_WEBHOOK_URL'):
        send_slack(tg_msg.replace('<b>', '*').replace('</b>', '*'))

    return True
