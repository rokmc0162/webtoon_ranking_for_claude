# JP 웹툰 랭킹 프로젝트 (RIVERSE)

## 프로젝트 개요
일본 웹툰/만화 플랫폼 12개에서 랭킹 데이터를 자동 크롤링하여 Supabase DB에 저장하고,
Next.js 대시보드로 시각화하는 시스템. 리버스(RIVERSE) 회사의 일본 시장 분석용.

## 시스템 구조
```
[크롤러 (macOS)] → [Supabase PostgreSQL (클라우드)] ← [Next.js 대시보드 (Vercel)]
     ↑                                                        ↑
  launchd 스케줄                                         git push → 자동 배포
  매일 9/15/21시 JST
```

- **크롤러**: macOS (Python 3 + Playwright + asyncio)
  - 프로젝트 경로: 이 저장소 루트
  - 실행: `scripts/run_crawler.sh` → launchd가 하루 3회 호출
  - 라인망가 앱: Android 폰 + ADB로 앱 크롤링 (USB 연결 필수)
- **대시보드**: Vercel 자동 배포
  - URL: webtoon-ranking-for-claude.vercel.app
  - Next.js 16 + TypeScript + Tailwind CSS 4 + shadcn/ui + Recharts
  - 소스: `dashboard-next/`
- **DB**: Supabase PostgreSQL (클라우드)
  - 크롤러와 대시보드가 동일 DB 사용

## 크롤링 대상 (12개 플랫폼)
| 플랫폼 | 에이전트 | 특이사항 |
|--------|----------|----------|
| 픽코마 (piccoma) | piccoma_agent.py | 일본IP 필수, Playwright |
| 라인망가 웹 (linemanga) | linemanga_agent.py | 일본IP 필수, Playwright |
| 라인망가 앱 (linemanga_app) | linemanga_app_agent.py | **Android 폰 + ADB 필수** |
| 메챠코믹 (mechacomic) | mechacomic_agent.py | Playwright |
| 코믹시모아 (cmoa) | cmoa_agent.py | Playwright |
| 코미코 (comico) | comico_agent.py | Playwright |
| 렌타 (renta) | renta_agent.py | Playwright |
| 북라이브 (booklive) | booklive_agent.py | Playwright |
| 이북재팬 (ebookjapan) | ebookjapan_agent.py | Playwright |
| 레진 (lezhin) | lezhin_agent.py | Playwright |
| 벨툰 (beltoon) | beltoon_agent.py | Playwright |
| U-NEXT (unext) | unext_agent.py | Playwright |

추가: Asura Scans (해적판 모니터링, 별도 실행)

## DB 구조 (Supabase PostgreSQL)
- `unified_works`: 작품 마스터 테이블 (title_kr UNIQUE KEY로 크로스 플랫폼 연결)
- `works`: 플랫폼별 작품 메타데이터 (platform + title PK, unified_work_id FK)
- `rankings`: 일별 랭킹 (date + platform + sub_category + rank PK)
- `reviews`: 리뷰 데이터 (platform + work_title + reviewer_name + reviewed_at PK)
- title_kr(한국어 제목)이 크로스 플랫폼 연결의 핵심 키

## 주요 디렉토리/파일
```
crawler/
  main.py              — 메인 크롤링 오케스트레이터
  main_external.py     — 외부 데이터 수집 (AniList, MAL, YouTube)
  main_asura.py        — Asura Scans 크롤링
  main_reviews.py      — 리뷰 수집
  orchestrator.py      — 병렬 크롤링 관리
  db.py                — Supabase CRUD
  utils.py             — title_kr 검증/번역, 유틸리티
  verify.py            — 데이터 검증/복구
  notify.py            — 텔레그램 알림
  agents/              — 12개 플랫폼 크롤러 에이전트

dashboard-next/        — Next.js 대시보드 (Vercel 배포)
  app/api/             — API 라우트
  components/          — UI 컴포넌트

data/
  title_mappings.json  — JP→KR 제목 매핑 (15,996개)
  riverse_titles.json  — 리버스 작품 목록

scripts/
  run_crawler.sh       — 크롤링 실행 (launchd에서 호출)
  health_check.sh      — 헬스체크
  setup_macmini.sh     — **맥미니 자동 셋업 스크립트** (아래 참조)
  fill_missing_title_kr.py — title_kr 일괄 번역

config/
  launchd/             — launchd plist 파일 5개
```

## 환경변수 (.env)
```
SUPABASE_DB_URL=postgresql://postgres.rvskgnyyqzgrkhzolxeq:Diddlf0162!@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres
TELEGRAM_BOT_TOKEN=8096768492:AAHvkre83GeEgRK4pVWKklcrqLXNhGEJHLc
TELEGRAM_CHAT_ID=8405582042
```

## 자동 크롤링 스케줄 (launchd)
`config/launchd/` 에 5개 plist 파일:
1. `com.riverse.webtoon-crawler.plist` — 매일 9/15/21시 크롤링
2. `com.riverse.webtoon-healthcheck.plist` — 매일 10시 헬스체크
3. `com.riverse.webtoon-awake.plist` — 절전 방지 (caffeinate)
4. `com.riverse.webtoon-dashboard.plist` — Streamlit 대시보드 (사용안함, Vercel로 대체)
5. `com.riverse.webtoon-tunnel.plist` — Cloudflare 터널 (사용안함)

실제 사용하는 것: 1, 2, 3번

## 맥미니 셋업 방법
```bash
# 1. 이 저장소를 클론하고
git clone https://github.com/rokmc0162/webtoon_ranking_for_claude.git
cd webtoon_ranking_for_claude

# 2. 자동 셋업 스크립트 실행
bash scripts/setup_macmini.sh
```
이 스크립트가 자동으로 처리하는 것:
- Python 의존성 설치 (pip)
- Playwright 브라우저 설치
- .env 파일 생성
- launchd plist 등록 (자동 크롤링 스케줄)
- 절전 방지 설정
- ADB 설치 (Android 폰 크롤링용)
- 로그 디렉토리 생성
- 테스트 크롤링 실행

## ADB (Android 폰) 연결
라인망가 앱 크롤링에 Android 폰이 필요:
1. USB로 폰을 맥미니에 연결
2. 폰에서 "USB 디버깅 허용" 팝업이 뜨면 승인
3. `adb devices` 로 연결 확인 (device 상태여야 함)
4. unauthorized면 → 폰에서 USB 디버깅 팝업 다시 승인

## 개발 워크플로우
1. 코드 수정 후 `git push` → Vercel 대시보드 자동 배포
2. 크롤러 코드 변경은 `run_crawler.sh`가 매회 `git pull`로 자동 반영
3. title_kr 관련: `validate_title_kr()` 함수가 품질 검증, 크롤링 시 자동 번역

## 핵심 기술 결정사항
- title_kr(한국어 제목): 크로스 플랫폼 연결 키. Google Translate API로 자동 번역
- unified_works 병합전략: author(첫 비빈값), description(최장), tags(합집합), is_riverse(OR)
- validate_title_kr(): 일본어 가나 포함, 음차 패턴, 정크 키 등 자동 차단
- 대시보드 트렌드 리포트: KPI만 기본 표시, 상세(리버스카드/마켓카드)는 토글

## 사용자 정보
- 사용자: 김양일 (RIVERSE 소속, 일본 사무실)
- 개발자가 아님 — 기술 설명은 간결하게, 자동화 우선
- 한국어로 소통
- 맥북에서 맥미니로 크롤러 이전 중 (2026-03-20)
