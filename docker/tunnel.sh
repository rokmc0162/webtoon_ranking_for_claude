#!/bin/bash
# Cloudflare Quick Tunnel — 컨테이너 내 실행
# Streamlit이 준비될 때까지 대기 후 터널 시작

TUNNEL_LOG="/app/logs/tunnel.log"
URL_FILE="/app/data/tunnel_url.txt"

# Streamlit 준비 대기 (최대 60초)
for i in $(seq 1 60); do
    if curl -s -o /dev/null http://localhost:8501 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Streamlit 준비 완료" >> "${TUNNEL_LOG}"
        break
    fi
    sleep 1
done

# cloudflared 실행 + URL 캡처
cloudflared tunnel --url http://localhost:8501 2>&1 | while IFS= read -r line; do
    echo "$line" >> "${TUNNEL_LOG}"
    if echo "$line" | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' > /dev/null 2>&1; then
        TUNNEL_URL=$(echo "$line" | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com')
        echo "$TUNNEL_URL" > "${URL_FILE}"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 공개 URL: ${TUNNEL_URL}" >> "${TUNNEL_LOG}"
    fi
done
