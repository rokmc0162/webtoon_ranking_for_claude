#!/bin/bash
# ============================================================
# 웹툰 랭킹 대시보드 - 외부 배포 설정 스크립트
# 이 스크립트 하나로 모든 설정이 완료됩니다
# ============================================================

set -e

PROJECT_DIR="/Users/kimyang-il/CLAUDE/webtoon_ranking_for_claude"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
CONFIG_DIR="${PROJECT_DIR}/config/launchd"

echo ""
echo "============================================================"
echo "  웹툰 랭킹 대시보드 - 외부 배포 설정"
echo "============================================================"
echo ""

# ---- 1. cloudflared 설치 확인 ----
echo "[1/5] cloudflared 설치 확인..."
if command -v cloudflared &>/dev/null; then
    echo "  ✅ cloudflared 설치됨 ($(cloudflared --version 2>&1 | head -1))"
else
    echo "  ⬇️  cloudflared 설치 중..."
    brew install cloudflare/cloudflare/cloudflared
    echo "  ✅ cloudflared 설치 완료"
fi
echo ""

# ---- 2. 스크립트 실행 권한 부여 ----
echo "[2/5] 스크립트 권한 설정..."
chmod +x "${PROJECT_DIR}/scripts/run_dashboard.sh"
chmod +x "${PROJECT_DIR}/scripts/run_tunnel.sh"
chmod +x "${PROJECT_DIR}/scripts/run_crawler.sh"
chmod +x "${PROJECT_DIR}/scripts/health_check.sh"
chmod +x "${PROJECT_DIR}/scripts/keep_awake.sh"
echo "  ✅ 실행 권한 설정 완료"
echo ""

# ---- 3. 로그/데이터 디렉토리 생성 ----
echo "[3/5] 디렉토리 생성..."
mkdir -p "${PROJECT_DIR}/logs"
mkdir -p "${PROJECT_DIR}/data"
echo "  ✅ logs/, data/ 디렉토리 확인"
echo ""

# ---- 4. 기존 서비스 정리 + 새 서비스 등록 ----
echo "[4/5] 서비스 등록 중..."
mkdir -p "${LAUNCH_AGENTS_DIR}"

# 등록할 서비스 목록
SERVICES=(
    "com.riverse.webtoon-awake"
    "com.riverse.webtoon-crawler"
    "com.riverse.webtoon-healthcheck"
    "com.riverse.webtoon-dashboard"
    "com.riverse.webtoon-tunnel"
)

for SERVICE in "${SERVICES[@]}"; do
    PLIST="${CONFIG_DIR}/${SERVICE}.plist"
    TARGET="${LAUNCH_AGENTS_DIR}/${SERVICE}.plist"

    if [ ! -f "$PLIST" ]; then
        echo "  ⚠️  ${SERVICE}.plist 파일 없음, 건너뜀"
        continue
    fi

    # 기존 서비스 언로드 (에러 무시)
    launchctl unload "$TARGET" 2>/dev/null || true

    # plist 복사 (동일 파일이면 삭제 후 복사)
    rm -f "$TARGET" 2>/dev/null || true
    cp "$PLIST" "$TARGET"

    # 서비스 로드
    launchctl load "$TARGET"
    echo "  ✅ ${SERVICE} 등록 완료"
done
echo ""

# ---- 5. 터널 URL 대기 ----
echo "[5/5] 터널 연결 대기 중..."
echo "  (Streamlit 시작 + Cloudflare 터널 연결에 약 15~30초 소요)"
echo ""

URL_FILE="${PROJECT_DIR}/data/tunnel_url.txt"
# 기존 URL 파일 삭제 (새 URL 생성 대기)
rm -f "$URL_FILE"

# 최대 60초 대기
for i in $(seq 1 60); do
    if [ -f "$URL_FILE" ] && [ -s "$URL_FILE" ]; then
        TUNNEL_URL=$(cat "$URL_FILE")
        echo ""
        echo "============================================================"
        echo ""
        echo "  🎉 배포 완료!"
        echo ""
        echo "  📌 공개 URL:"
        echo "  ${TUNNEL_URL}"
        echo ""
        echo "  이 URL을 공유하면 누구나 대시보드에 접속할 수 있습니다."
        echo ""
        echo "============================================================"
        echo ""
        echo "  서비스 상태 확인: launchctl list | grep riverse"
        echo "  터널 로그 확인:   tail -f ${PROJECT_DIR}/logs/tunnel.log"
        echo "  URL 다시 확인:    cat ${URL_FILE}"
        echo ""
        exit 0
    fi
    printf "\r  대기 중... %d초" "$i"
    sleep 1
done

echo ""
echo ""
echo "  ⏳ 터널 URL 생성에 시간이 더 걸리고 있습니다."
echo "  잠시 후 아래 명령어로 URL을 확인해주세요:"
echo ""
echo "  cat ${URL_FILE}"
echo ""
echo "  또는 로그를 확인해주세요:"
echo "  tail -20 ${PROJECT_DIR}/logs/tunnel.log"
echo ""
