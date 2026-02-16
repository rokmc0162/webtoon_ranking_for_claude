#!/bin/bash
# =============================================================================
# Synology NAS 배포 스크립트
# 맥에서 실행: bash scripts/deploy_synology.sh
# =============================================================================

set -e

# 프로젝트 경로
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_CONF="${PROJECT_DIR}/.deploy_config"

echo "============================================"
echo "  웹툰 랭킹 → Synology NAS 배포"
echo "============================================"
echo ""

# 설정 파일에서 이전 값 로드
if [ -f "$DEPLOY_CONF" ]; then
    source "$DEPLOY_CONF"
fi

# SSH 접속 정보 입력 (이전 값이 있으면 기본값으로 표시)
read -p "NAS IP 또는 호스트명 [${NAS_HOST:-}]: " input_host
NAS_HOST="${input_host:-$NAS_HOST}"

read -p "SSH 포트 [${NAS_PORT:-1120}]: " input_port
NAS_PORT="${input_port:-${NAS_PORT:-1120}}"

read -p "SSH 사용자명 [${NAS_USER:-admin}]: " input_user
NAS_USER="${input_user:-${NAS_USER:-admin}}"

read -p "NAS 배포 경로 [${NAS_PATH:-/volume1/docker/webtoon}]: " input_path
NAS_PATH="${input_path:-${NAS_PATH:-/volume1/docker/webtoon}}"

if [ -z "$NAS_HOST" ]; then
    echo "❌ NAS 호스트를 입력해주세요."
    exit 1
fi

# 설정 저장 (다음 배포 시 재사용)
cat > "$DEPLOY_CONF" << EOF
NAS_HOST="${NAS_HOST}"
NAS_PORT="${NAS_PORT}"
NAS_USER="${NAS_USER}"
NAS_PATH="${NAS_PATH}"
EOF

SSH_CMD="ssh -p ${NAS_PORT} ${NAS_USER}@${NAS_HOST}"
SCP_CMD="scp -P ${NAS_PORT}"

echo ""
echo "📡 접속 정보: ${NAS_USER}@${NAS_HOST}:${NAS_PORT}"
echo "📂 배포 경로: ${NAS_PATH}"
echo ""

# 1. SSH 연결 테스트
echo "🔗 SSH 연결 테스트..."
if ! ${SSH_CMD} "echo 'OK'" 2>/dev/null; then
    echo "❌ SSH 연결 실패. 접속 정보를 확인해주세요."
    echo "   ssh -p ${NAS_PORT} ${NAS_USER}@${NAS_HOST}"
    exit 1
fi
echo "   ✅ 연결 성공"

# 2. NAS에 배포 디렉토리 생성
echo ""
echo "📁 배포 디렉토리 준비..."
${SSH_CMD} "mkdir -p ${NAS_PATH}/data ${NAS_PATH}/logs"
echo "   ✅ ${NAS_PATH} 준비 완료"

# 3. 프로젝트 파일 전송 (rsync)
echo ""
echo "📦 프로젝트 파일 전송 중..."
rsync -avz --progress \
    -e "ssh -p ${NAS_PORT}" \
    --exclude='.git' \
    --exclude='venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='logs/' \
    --exclude='config/launchd/' \
    --exclude='.claude/' \
    --exclude='.deploy_config' \
    --exclude='data/rankings.db' \
    --exclude='data/backup/' \
    "${PROJECT_DIR}/" "${NAS_USER}@${NAS_HOST}:${NAS_PATH}/"
echo "   ✅ 프로젝트 파일 전송 완료"

# 4. 데이터 파일 전송 (DB + JSON)
echo ""
echo "💾 데이터 파일 전송 중..."
rsync -avz --progress \
    -e "ssh -p ${NAS_PORT}" \
    "${PROJECT_DIR}/data/rankings.db" \
    "${PROJECT_DIR}/data/title_mappings.json" \
    "${PROJECT_DIR}/data/riverse_titles.json" \
    "${NAS_USER}@${NAS_HOST}:${NAS_PATH}/data/"

if [ -d "${PROJECT_DIR}/data/backup" ]; then
    rsync -avz --progress \
        -e "ssh -p ${NAS_PORT}" \
        "${PROJECT_DIR}/data/backup/" \
        "${NAS_USER}@${NAS_HOST}:${NAS_PATH}/data/backup/"
fi
echo "   ✅ 데이터 전송 완료"

# 5. Docker 빌드 + 실행
echo ""
echo "🐳 Docker 컨테이너 빌드 및 실행..."
${SSH_CMD} "cd ${NAS_PATH} && docker compose down 2>/dev/null; docker compose up -d --build"
echo "   ✅ 컨테이너 시작됨"

# 6. 터널 URL 대기 (최대 90초)
echo ""
echo "🌐 공개 URL 생성 대기 중..."
for i in $(seq 1 90); do
    TUNNEL_URL=$(${SSH_CMD} "cat ${NAS_PATH}/data/tunnel_url.txt 2>/dev/null" 2>/dev/null)
    if [ -n "$TUNNEL_URL" ] && echo "$TUNNEL_URL" | grep -q "trycloudflare.com"; then
        break
    fi
    sleep 1
    printf "\r   대기 중... ${i}초"
done
echo ""

# 7. 결과 출력
echo ""
echo "============================================"
if [ -n "$TUNNEL_URL" ] && echo "$TUNNEL_URL" | grep -q "trycloudflare.com"; then
    echo "  ✅ 배포 완료!"
    echo ""
    echo "  🌐 공개 URL: ${TUNNEL_URL}"
    echo "  📊 직접 접속: http://${NAS_HOST}:8501"
else
    echo "  ⚠️ 배포 완료 (터널 URL 확인 필요)"
    echo ""
    echo "  📊 직접 접속: http://${NAS_HOST}:8501"
    echo "  🔍 로그 확인: ${SSH_CMD} \"docker logs webtoon-ranking\""
fi
echo ""
echo "  📋 유용한 명령어:"
echo "  로그 보기:     ${SSH_CMD} \"docker logs -f webtoon-ranking\""
echo "  수동 크롤링:   ${SSH_CMD} \"docker exec webtoon-ranking python3 crawler/main.py\""
echo "  컨테이너 중지: ${SSH_CMD} \"cd ${NAS_PATH} && docker compose down\""
echo "  컨테이너 재시작: ${SSH_CMD} \"cd ${NAS_PATH} && docker compose restart\""
echo "============================================"
