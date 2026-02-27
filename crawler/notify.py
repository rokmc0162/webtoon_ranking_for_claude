"""
Slack 알림 모듈 - 크롤링 완료 시 결과를 Slack으로 전송

설정:
    .env에 SLACK_WEBHOOK_URL 추가

    Slack 앱 설정 방법:
    1. https://api.slack.com/apps → Create New App
    2. Incoming Webhooks → Activate → Add New Webhook to Workspace
    3. 채널 선택 → Webhook URL 복사
    4. .env에 SLACK_WEBHOOK_URL=https://hooks.slack.com/services/... 추가
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, Optional


def send_slack(message: str, webhook_url: Optional[str] = None) -> bool:
    """Slack으로 메시지 전송 (외부 의존성 없이 urllib만 사용)"""
    url = webhook_url or os.environ.get('SLACK_WEBHOOK_URL', '')
    if not url:
        return False

    payload = json.dumps({"text": message}).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except (urllib.error.URLError, Exception) as e:
        print(f"⚠️  Slack 전송 실패: {e}")
        return False


def notify_crawl_complete(results: Dict, elapsed_seconds: float = 0) -> bool:
    """
    크롤링 완료 알림을 Slack으로 전송

    Args:
        results: {platform_id: AgentResult} 딕셔너리
        elapsed_seconds: 총 소요 시간 (초)
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    success = []
    failed = []
    total_count = 0

    for platform, result in sorted(results.items()):
        if result.success:
            success.append(f"  • {platform}: {result.count}개")
            total_count += result.count
        else:
            err = (result.error or "알 수 없는 오류")[:80]
            failed.append(f"  • {platform}: {err}")

    # 시간 포맷
    if elapsed_seconds > 0:
        mins, secs = divmod(int(elapsed_seconds), 60)
        time_str = f"{mins}분 {secs}초" if mins else f"{secs}초"
    else:
        time_str = "-"

    # 메시지 구성
    lines = []
    if failed:
        lines.append(f"⚠️ *크롤링 완료* ({now})")
    else:
        lines.append(f"✅ *크롤링 완료* ({now})")

    lines.append(f"📊 수집: {total_count}개 | ⏱ {time_str}")
    lines.append("")

    if success:
        lines.append(f"*성공 ({len(success)}개 플랫폼):*")
        lines.extend(success)

    if failed:
        lines.append("")
        lines.append(f"*❌ 실패 ({len(failed)}개 플랫폼):*")
        lines.extend(failed)

    message = "\n".join(lines)
    return send_slack(message)
