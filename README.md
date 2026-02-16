# 일본 웹툰 랭킹 크롤링 시스템

일본 4대 웹툰 플랫폼(픽코마, 라인망가, 메챠코믹, 코믹시모아)의 일일 랭킹을 자동 수집하고, 순위 변동을 시각화하는 시스템입니다.

## 주요 기능

- ✅ 4개 플랫폼 상위 50위 랭킹 자동 수집
- ✅ SQLite에 일일 데이터 누적 저장
- ✅ 특정 작품의 순위 변동 그래프 시각화 (핵심!)
- ✅ 리버스 작품 자동 하이라이트
- ✅ 일본어/한국어 제목 병행 표기

## 기술 스택

- **Python 3.8+**
- **Playwright** - 브라우저 자동화 (CSR 크롤링)
- **BeautifulSoup** - HTML 파싱
- **Streamlit** - 대시보드 UI
- **Plotly** - 그래프 시각화
- **SQLite** - 로컬 데이터베이스

## 설치

### 1. 가상환경 생성 및 활성화

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. 데이터 준비

```bash
# 리버스 작품 리스트 추출
python3 scripts/extract_riverse_titles.py

# DB 초기화
python3 -c "from crawler.db import init_db; init_db()"
```

## 실행

### 크롤링 실행

```bash
python3 crawler/main.py
```

### 대시보드 실행

```bash
streamlit run dashboard/app.py
# 또는:
./run_dashboard.sh  # Linux/Mac
run_dashboard.bat   # Windows

# 브라우저 자동 오픈: http://localhost:8501
```

**대시보드 기능:**
- 📅 날짜별 랭킹 조회
- 🎯 4개 플랫폼 탭 (픽코마, 라인망가, 메챠코믹, 코믹시모아)
- ⭐ 리버스 작품 필터링
- 📈 작품별 순위 변동 그래프 (일일 누적)
- 🔗 작품 페이지 바로가기 링크
- 📊 전날 대비 순위 변동 표시 (⬆️⬇️🆕)

## 자동 실행 설정 (Cron)

매일 JST 09:00에 자동으로 크롤링:

```bash
crontab -e
# 추가:
0 9 * * * cd ~/webtoon-ranking && ~/webtoon-ranking/venv/bin/python3 crawler/main.py >> logs/cron.log 2>&1
```

## 프로젝트 구조

```
webtoon_ranking_for_claude/
├── crawler/
│   ├── main.py              # 크롤러 메인
│   ├── db.py                # SQLite 저장 로직
│   ├── utils.py             # 공통 유틸리티
│   └── platforms/
│       ├── piccoma.py       # 픽코마 크롤러
│       ├── linemanga.py     # 라인망가 크롤러
│       ├── mechacomic.py    # 메챠코믹 크롤러
│       └── cmoa.py          # 코믹시모아 크롤러
├── dashboard/
│   └── app.py               # Streamlit 대시보드
├── data/
│   ├── riverse_titles.json  # 리버스 작품 리스트
│   ├── title_mappings.json  # 한국어 제목 매핑
│   └── backup/              # JSON 백업
├── logs/
└── scripts/
    └── extract_riverse_titles.py
```

## 주의사항

### IP 제한

- **픽코마, 라인망가**: 일본 IP 필수
  - 한국에서 403 에러 발생 시 일본 VPN 사용
- **메챠코믹, 코믹시모아**: IP 제한 없음

### CSR 크롤링 (라인망가)

- JavaScript 렌더링 대기 필수
- 일반 HTTP 요청으로는 데이터 수집 불가

## 라이선스

MIT License

## 문의

RIVERSE Inc. 기술팀
