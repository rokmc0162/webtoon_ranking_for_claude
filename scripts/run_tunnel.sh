#!/bin/bash
# Cloudflare Tunnel 실행 스크립트
# launchd에서 호출됨 - cloudflared Quick Tunnel 실행 및 URL 캡처

# 환경 설정
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

# 프로젝트 경로
PROJECT_DIR="/Users/kimyang-il/CLAUDE/webtoon_ranking_for_claude"
LOG_DIR="${PROJECT_DIR}/logs"
TUNNEL_LOG="${LOG_DIR}/tunnel.log"
URL_FILE="${PROJECT_DIR}/data/tunnel_url.txt"

mkdir -p "${LOG_DIR}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 터널 시작 중..." >> "${TUNNEL_LOG}"

# Streamlit이 준비될 때까지 대기 (최대 30초)
for i in $(seq 1 30); do
    if curl -s -o /dev/null http://localhost:8501 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Streamlit 준비 완료" >> "${TUNNEL_LOG}"
        break
    fi
    sleep 1
done

# cloudflared 실행 (stderr에서 URL 추출)
# Quick Tunnel은 stderr로 URL을 출력함
/usr/local/bin/cloudflared tunnel --url http://localhost:8501 2>&1 | while IFS= read -r line; do
    echo "$line" >> "${TUNNEL_LOG}"
    # URL 추출: "https://xxx.trycloudflare.com" 패턴
    if echo "$line" | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' > /dev/null 2>&1; then
        TUNNEL_URL=$(echo "$line" | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com')
        echo "$TUNNEL_URL" > "${URL_FILE}"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 공개 URL: ${TUNNEL_URL}" >> "${TUNNEL_LOG}"
        # macOS 알림
        osascript -e "display notification \"${TUNNEL_URL}\" with title \"웹툰 대시보드 공개 URL\"" 2>/dev/null
    fi
done
