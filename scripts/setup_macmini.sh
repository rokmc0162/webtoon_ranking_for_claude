#!/bin/bash
# =============================================================================
# 웹툰 랭킹 크롤러 — 맥미니 자동 셋업 스크립트
# 실행: bash scripts/setup_macmini.sh
#
# 이 스크립트가 하는 일:
# 1. Python 의존성 설치
# 2. Playwright 브라우저 설치
# 3. .env 파일 생성
# 4. ADB (Android Debug Bridge) 설치
# 5. launchd 자동 크롤링 스케줄 등록
# 6. 절전 방지 설정
# 7. 테스트 크롤링
# =============================================================================
set -e

# 프로젝트 경로 (이 스크립트가 있는 위치 기준)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CURRENT_USER="$(whoami)"
HOME_DIR="$HOME"

echo "=========================================="
echo " 웹툰 랭킹 크롤러 — 맥미니 셋업"
echo " 프로젝트: ${PROJECT_DIR}"
echo " 사용자: ${CURRENT_USER}"
echo "=========================================="
echo ""

# -----------------------------------------------
# 1. Homebrew (없으면 설치)
# -----------------------------------------------
if ! command -v brew &>/dev/null; then
    echo "[1/7] Homebrew 설치 중..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    fi
else
    echo "[1/7] Homebrew OK"
fi

# -----------------------------------------------
# 2. Python 의존성 설치
# -----------------------------------------------
echo "[2/7] Python 의존성 설치 중..."
pip3 install --user --upgrade pip 2>/dev/null || true
pip3 install --user -r "${PROJECT_DIR}/requirements.txt"
echo "  의존성 설치 완료"

# -----------------------------------------------
# 3. Playwright 브라우저 설치
# -----------------------------------------------
echo "[3/7] Playwright Chromium 설치 중..."
python3 -m playwright install chromium 2>/dev/null || playwright install chromium 2>/dev/null || echo "  ⚠️  Playwright 설치 실패 — 수동 설치 필요: python3 -m playwright install chromium"
echo "  Playwright 설치 완료"

# -----------------------------------------------
# 4. .env 파일 생성
# -----------------------------------------------
ENV_FILE="${PROJECT_DIR}/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "[4/7] .env 파일 생성 중..."
    cat > "$ENV_FILE" << 'ENVEOF'
SUPABASE_DB_URL=postgresql://postgres.rvskgnyyqzgrkhzolxeq:Diddlf0162!@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres
TELEGRAM_BOT_TOKEN=8096768492:AAHvkre83GeEgRK4pVWKklcrqLXNhGEJHLc
TELEGRAM_CHAT_ID=8405582042
ENVEOF
    echo "  .env 생성 완료"
else
    echo "[4/7] .env 이미 존재함"
fi

# -----------------------------------------------
# 5. ADB 설치 (라인망가 앱 크롤링용)
# -----------------------------------------------
echo "[5/7] ADB (Android Debug Bridge) 설치 확인..."
if ! command -v adb &>/dev/null; then
    echo "  ADB 설치 중..."
    brew install --cask android-platform-tools 2>/dev/null || brew install android-platform-tools 2>/dev/null || echo "  ⚠️  ADB 설치 실패 — 수동 설치 필요: brew install android-platform-tools"
else
    echo "  ADB OK: $(adb version | head -1)"
fi

# 폰 연결 확인
echo "  폰 연결 확인..."
ADB_DEVICES=$(adb devices 2>/dev/null | grep -v "List" | grep -v "^$" || true)
if [ -n "$ADB_DEVICES" ]; then
    echo "  연결된 기기: $ADB_DEVICES"
    if echo "$ADB_DEVICES" | grep -q "unauthorized"; then
        echo "  ⚠️  폰에서 'USB 디버깅 허용' 팝업을 승인해주세요!"
    fi
else
    echo "  ⚠️  연결된 폰 없음 — 라인망가 앱 크롤링을 위해 USB 연결 필요"
fi

# -----------------------------------------------
# 6. launchd 스케줄 등록
# -----------------------------------------------
echo "[6/7] launchd 자동 크롤링 스케줄 등록..."

LAUNCH_AGENTS_DIR="${HOME_DIR}/Library/LaunchAgents"
mkdir -p "${LAUNCH_AGENTS_DIR}"
mkdir -p "${PROJECT_DIR}/logs"

# run_crawler.sh 경로를 현재 환경에 맞게 업데이트
PYTHON3_PATH="$(which python3)"
ADB_PATH="$(which adb 2>/dev/null || echo '/usr/local/bin/adb')"

# run_crawler.sh 재생성 (현재 사용자 경로에 맞게)
cat > "${PROJECT_DIR}/scripts/run_crawler.sh" << RUNEOF
#!/bin/bash
# 웹툰 랭킹 크롤러 실행 스크립트
# launchd에서 호출됨

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:\$PATH"
export LANG=ko_KR.UTF-8
export HOME="${HOME_DIR}"

PROJECT_DIR="${PROJECT_DIR}"
LOG_DIR="\${PROJECT_DIR}/logs"
LOG_FILE="\${LOG_DIR}/crawler_\$(date +%Y-%m-%d).log"

mkdir -p "\${LOG_DIR}"

cd "\${PROJECT_DIR}"
set -a
source .env 2>/dev/null || true
set +a

git pull origin main --quiet 2>/dev/null || true

echo "" >> "\${LOG_FILE}"
echo "========================================" >> "\${LOG_FILE}"
echo "[\$(date '+%Y-%m-%d %H:%M:%S')] 크롤러 실행 시작" >> "\${LOG_FILE}"
echo "========================================" >> "\${LOG_FILE}"

${PYTHON3_PATH} crawler/main.py >> "\${LOG_FILE}" 2>&1
EXIT_CODE=\$?
echo "[\$(date '+%Y-%m-%d %H:%M:%S')] 랭킹 크롤링 완료 (exit: \${EXIT_CODE})" >> "\${LOG_FILE}"

echo "[\$(date '+%Y-%m-%d %H:%M:%S')] 외부 데이터 수집 시작..." >> "\${LOG_FILE}"
${PYTHON3_PATH} crawler/main_external.py --max-works 200 >> "\${LOG_FILE}" 2>&1
echo "[\$(date '+%Y-%m-%d %H:%M:%S')] 외부 데이터 수집 완료" >> "\${LOG_FILE}"

echo "[\$(date '+%Y-%m-%d %H:%M:%S')] Asura Scans 크롤링 시작..." >> "\${LOG_FILE}"
${PYTHON3_PATH} crawler/main_asura.py --phase rankings >> "\${LOG_FILE}" 2>&1
${PYTHON3_PATH} crawler/main_asura.py --phase series >> "\${LOG_FILE}" 2>&1
echo "[\$(date '+%Y-%m-%d %H:%M:%S')] Asura Scans 크롤링 완료" >> "\${LOG_FILE}"

echo "[\$(date '+%Y-%m-%d %H:%M:%S')] 모든 크롤링 완료" >> "\${LOG_FILE}"

find "\${LOG_DIR}" -name "crawler_*.log" -mtime +30 -delete 2>/dev/null
exit \${EXIT_CODE}
RUNEOF
chmod +x "${PROJECT_DIR}/scripts/run_crawler.sh"

# health_check.sh도 경로 업데이트
cat > "${PROJECT_DIR}/scripts/health_check.sh" << HCEOF
#!/bin/bash
PROJECT_DIR="${PROJECT_DIR}"
LOG_DIR="\${PROJECT_DIR}/logs"
HEALTH_LOG="\${LOG_DIR}/health_\$(date +%Y-%m-%d).log"
TODAY=\$(date +%Y-%m-%d)

mkdir -p "\${LOG_DIR}"
echo "[\$(date '+%Y-%m-%d %H:%M:%S')] 헬스체크 시작" >> "\${HEALTH_LOG}"

cd "\${PROJECT_DIR}"
set -a
source .env 2>/dev/null || true
set +a

# Supabase DB 확인 (psql)
COUNT=\$(${PYTHON3_PATH} -c "
import os, psycopg2
conn = psycopg2.connect(os.environ['SUPABASE_DB_URL'])
cur = conn.cursor()
cur.execute(\"SELECT COUNT(*) FROM rankings WHERE date='\${TODAY}'\")
print(cur.fetchone()[0])
conn.close()
" 2>/dev/null || echo "0")

if [ "\${COUNT}" -eq 0 ] 2>/dev/null; then
    echo "  FAIL: 오늘(\${TODAY}) 수집된 데이터 없음" >> "\${HEALTH_LOG}"
    osascript -e "display notification \"오늘(\${TODAY}) 데이터가 없습니다!\" with title \"웹툰 크롤러 경고\"" 2>/dev/null
else
    echo "  OK: 오늘(\${TODAY}) \${COUNT}개 수집" >> "\${HEALTH_LOG}"
    osascript -e "display notification \"오늘 \${COUNT}개 수집 완료\" with title \"웹툰 크롤러 정상\"" 2>/dev/null
fi

echo "[\$(date '+%Y-%m-%d %H:%M:%S')] 헬스체크 완료" >> "\${HEALTH_LOG}"
HCEOF
chmod +x "${PROJECT_DIR}/scripts/health_check.sh"

# plist 파일들을 현재 사용자 경로로 업데이트 후 설치
for PLIST_NAME in com.riverse.webtoon-crawler com.riverse.webtoon-healthcheck com.riverse.webtoon-awake; do
    SRC="${PROJECT_DIR}/config/launchd/${PLIST_NAME}.plist"
    DST="${LAUNCH_AGENTS_DIR}/${PLIST_NAME}.plist"

    if [ -f "$SRC" ]; then
        # 기존 plist 언로드 (오류 무시)
        launchctl unload "$DST" 2>/dev/null || true

        # 경로를 현재 사용자에 맞게 변환
        sed "s|/Users/kimyang-il/CLAUDE/webtoon_ranking_for_claude|${PROJECT_DIR}|g; s|/Users/kimyang-il|${HOME_DIR}|g" "$SRC" > "$DST"

        # 로드
        launchctl load "$DST"
        echo "  등록: ${PLIST_NAME}"
    fi
done

echo "  launchd 등록 완료 (크롤러: 9/15/21시, 헬스체크: 10시, 절전방지: 항상)"

# -----------------------------------------------
# 7. 절전 방지
# -----------------------------------------------
echo "[7/7] 절전 방지 설정..."
sudo pmset -a disablesleep 1 2>/dev/null || echo "  ⚠️  sudo 권한 필요 — 수동 실행: sudo pmset -a disablesleep 1"
sudo pmset -a sleep 0 2>/dev/null || true
sudo pmset -a hibernatemode 0 2>/dev/null || true
sudo pmset -a displaysleep 10 2>/dev/null || true
echo "  절전 비활성화 완료 (디스플레이만 10분 후 꺼짐)"

# -----------------------------------------------
# 완료
# -----------------------------------------------
echo ""
echo "=========================================="
echo " 셋업 완료!"
echo "=========================================="
echo ""
echo " 자동 크롤링: 매일 9시/15시/21시 JST"
echo " 헬스체크:    매일 10시"
echo " 대시보드:    webtoon-ranking-for-claude.vercel.app"
echo " 로그:        ${PROJECT_DIR}/logs/"
echo ""
echo " 확인 명령어:"
echo "   launchctl list | grep riverse    # 등록 확인"
echo "   adb devices                      # 폰 연결 확인"
echo "   python3 crawler/main.py          # 수동 크롤링 테스트"
echo ""

# 테스트 크롤링 (선택)
read -p " 테스트 크롤링을 실행하시겠습니까? (y/N) " TEST_RUN
if [ "$TEST_RUN" = "y" ] || [ "$TEST_RUN" = "Y" ]; then
    echo " 테스트 크롤링 실행 중..."
    cd "${PROJECT_DIR}"
    set -a
    source .env 2>/dev/null || true
    set +a
    ${PYTHON3_PATH} crawler/main.py
fi
