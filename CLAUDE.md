# JP 웹툰 랭킹 프로젝트

## 시스템 구조
- **대시보드**: Vercel 배포 (GitHub push → 자동 배포)
  - URL: webtoon-ranking-for-claude.vercel.app
  - Next.js 16 + TypeScript + Tailwind CSS 4 + shadcn/ui + Recharts
  - Root Directory: `dashboard-next/`
- **크롤러**: macOS 맥북 (일본 사무실, cron 9/15/21시)
  - Python 3 + Playwright + asyncio
  - 프로젝트 경로: `~/webtoon_ranking`
  - cron 스크립트: `scripts/run_crawl_mac.sh` (실행 시 git pull 자동)
- **DB**: Supabase PostgreSQL (클라우드)

## 크롤링 대상 (4개 플랫폼)
1. 픽코마 (piccoma) - 일본IP 필수
2. 라인망가 (linemanga) - 일본IP 필수
3. 메챠코믹 (mechacomic)
4. 코믹시모아 (cmoa)

## 주요 디렉토리
- `crawler/agents/` — 4개 플랫폼 크롤러
- `crawler/db.py` — Supabase CRUD
- `crawler/main.py` — 랭킹 크롤링 메인
- `crawler/main_reviews.py` — 리뷰 수집 메인
- `dashboard-next/` — Next.js 대시보드
- `dashboard-next/app/api/` — API 라우트
- `scripts/` — 실행/설치 스크립트

## 개발 워크플로우
1. 이 PC 또는 맥북에서 코드 수정
2. `git push` → Vercel 대시보드 자동 배포
3. 크롤러 변경은 다음 cron 실행 시 `git pull`로 자동 반영

## 환경변수 (.env)
- `SUPABASE_DB_URL` — PostgreSQL 연결 문자열
- `NEXT_PUBLIC_SUPABASE_URL` — Supabase 프로젝트 URL
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — Supabase 공개 키
