#!/bin/sh
# Cloudflare Quick Tunnel — 컨테이너 내 실행

TUNNEL_LOG="/app/logs/tunnel.log"
URL_FILE="/app/data/tunnel_url.txt"

# Next.js 준비 대기 (최대 60초)
i=0
while [ $i -lt 60 ]; do
    if curl -s -o /dev/null http://localhost:3000 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Next.js 준비 완료" >> "${TUNNEL_LOG}"
        break
    fi
    i=$((i + 1))
    sleep 1
done

# cloudflared 실행 + URL 캡처
cloudflared tunnel --url http://localhost:3000 2>&1 | while IFS= read -r line; do
    echo "$line" >> "${TUNNEL_LOG}"
    TUNNEL_URL=$(echo "$line" | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com')
    if [ -n "$TUNNEL_URL" ]; then
        echo "$TUNNEL_URL" > "${URL_FILE}"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 공개 URL: ${TUNNEL_URL}" >> "${TUNNEL_LOG}"
    fi
done
