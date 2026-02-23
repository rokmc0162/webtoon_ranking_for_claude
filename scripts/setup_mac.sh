#!/bin/bash
# =============================================================================
# 웹툰 랭킹 크롤러 — macOS 자동 설치 스크립트
# 맥북 터미널에서 실행: bash setup_mac.sh
# =============================================================================
set -e

echo "=========================================="
echo " 웹툰 랭킹 크롤러 설치 시작"
echo "=========================================="

# 1. Homebrew 설치 (없으면)
if ! command -v brew &>/dev/null; then
    echo "[1/6] Homebrew 설치 중..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Apple Silicon Mac용 PATH 설정
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    fi
else
    echo "[1/6] Homebrew 이미 설치됨"
fi

# 2. Python 설치
if ! command -v python3 &>/dev/null; then
    echo "[2/6] Python 설치 중..."
    brew install python
else
    echo "[2/6] Python 이미 설치됨: $(python3 --version)"
fi

# 3. 프로젝트 디렉토리 설정
PROJECT_DIR="$HOME/webtoon_ranking"
echo "[3/6] 프로젝트 설정: $PROJECT_DIR"

if [ -d "$PROJECT_DIR" ]; then
    cd "$PROJECT_DIR"
    git pull origin main
else
    git clone https://github.com/rokmc0162/webtoon_ranking_for_claude.git "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# 4. Python 가상환경 + 의존성
echo "[4/6] Python 의존성 설치 중..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Playwright 브라우저 설치
echo "[5/6] Playwright Chromium 설치 중..."
playwright install chromium

# 6. .env 파일 생성
ENV_FILE="$PROJECT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "[6/6] .env 파일 생성 중..."
    cat > "$ENV_FILE" << 'ENVEOF'
SUPABASE_DB_URL=postgresql://postgres.rvskgnyyqzgrkhzolxeq:Diddlf0162!@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres
NEXT_PUBLIC_SUPABASE_URL=https://rvskgnyyqzgrkhzolxeq.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJ2c2tnbnl5cXpncmtoem9seGVxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mzk3ODkxMDgsImV4cCI6MjA1NTM2NTEwOH0.sb_publishable_qJl9ykqDlSiZelyYQrVvnA_CBldxBlB
ENVEOF
    echo "  .env 생성 완료"
else
    echo "[6/6] .env 이미 존재함"
fi

# 7. macOS 절전 비활성화
echo ""
echo "=========================================="
echo " 절전 모드 비활성화 (관리자 비밀번호 필요)"
echo "=========================================="
sudo pmset -a disablesleep 1
sudo pmset -a sleep 0
sudo pmset -a hibernatemode 0
sudo pmset -a displaysleep 10
echo "  절전 비활성화 완료 (디스플레이만 10분 후 꺼짐)"

# 8. cron 등록
echo ""
echo "=========================================="
echo " 크롤링 스케줄 등록"
echo "=========================================="

CRON_SCRIPT="$PROJECT_DIR/scripts/run_crawl_mac.sh"
cat > "$CRON_SCRIPT" << CRONEOF
#!/bin/bash
cd "$PROJECT_DIR"
source venv/bin/activate
export \$(cat .env | xargs)
python3 crawler/main.py >> "$PROJECT_DIR/logs/crawler_\$(date +%Y-%m-%d).log" 2>&1
CRONEOF
chmod +x "$CRON_SCRIPT"

# logs 디렉토리
mkdir -p "$PROJECT_DIR/logs"

# crontab 등록 (기존 다른 작업 유지)
EXISTING_CRON=$(crontab -l 2>/dev/null || true)
if echo "$EXISTING_CRON" | grep -q "webtoon_ranking"; then
    echo "  cron 이미 등록되어 있음"
else
    (echo "$EXISTING_CRON"; echo "# 웹툰 랭킹 크롤러 (JST 9시/15시/21시)"; echo "0 9,15,21 * * * $CRON_SCRIPT"; echo "# 주간 리뷰 수집 (월요일 01시)"; echo "0 1 * * 1 cd $PROJECT_DIR && source venv/bin/activate && export \$(cat .env | xargs) && python3 crawler/main_reviews.py >> $PROJECT_DIR/logs/reviews_\$(date +\\%Y-\\%m-\\%d).log 2>&1") | crontab -
    echo "  cron 등록 완료:"
    echo "    - 매일 9시/15시/21시: 랭킹 크롤링"
    echo "    - 매주 월요일 01시: 리뷰 수집"
fi

# 9. 테스트 실행
echo ""
echo "=========================================="
echo " 설치 완료! 테스트 크롤링 실행 중..."
echo "=========================================="
source venv/bin/activate
export $(cat .env | xargs)
python3 crawler/main.py

echo ""
echo "=========================================="
echo " 모든 설정 완료!"
echo " 크롤러: 매일 9/15/21시 자동 실행"
echo " 대시보드: Vercel에서 확인"
echo "=========================================="
