# =============================================================================
# 웹툰 랭킹 크롤러 + 대시보드 Docker 이미지
# 베이스: Microsoft Playwright (Python + Chromium 포함)
# =============================================================================

FROM mcr.microsoft.com/playwright/python:v1.50.0-noble

# 타임존 설정 (일본 시간 기준 크롤링 스케줄)
ENV TZ=Asia/Tokyo
ENV LANG=ko_KR.UTF-8
ENV PYTHONUNBUFFERED=1

# cron + 로케일 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    locales \
    curl \
    && sed -i '/ko_KR.UTF-8/s/^# //g' /etc/locale.gen \
    && locale-gen ko_KR.UTF-8 \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# cloudflared 설치 (linux-amd64)
RUN curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb \
    -o /tmp/cloudflared.deb \
    && dpkg -i /tmp/cloudflared.deb \
    && rm /tmp/cloudflared.deb

# 작업 디렉토리
WORKDIR /app

# Python 의존성 설치 (캐시 레이어 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치 (이미지에 포함되어 있지만 버전 맞추기)
RUN playwright install chromium

# 프로젝트 파일 복사
COPY crawler/ ./crawler/
COPY dashboard/ ./dashboard/
COPY docs/ ./docs/
COPY .streamlit/ ./.streamlit/
COPY docker/ ./docker/

# crontab 등록
COPY docker/crontab /etc/cron.d/webtoon-cron
RUN chmod 0644 /etc/cron.d/webtoon-cron \
    && crontab /etc/cron.d/webtoon-cron

# 데이터/로그 디렉토리 (볼륨 마운트 포인트)
RUN mkdir -p /app/data /app/logs

# entrypoint 설정
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8501

ENTRYPOINT ["/entrypoint.sh"]
