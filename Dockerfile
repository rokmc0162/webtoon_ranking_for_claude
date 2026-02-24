# =============================================================================
# 웹툰 랭킹 대시보드 Docker 이미지 (경량)
# 베이스: node:20-alpine (~50MB)
# NAS에서는 대시보드 + Cloudflare 터널만 실행
# 크롤러는 PC에서 Task Scheduler로 별도 실행
# =============================================================================

FROM node:20-alpine

ENV TZ=Asia/Tokyo
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# curl + tzdata 설치
RUN apk add --no-cache curl tzdata \
    && cp /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone

# cloudflared 바이너리 설치
RUN curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
    -o /usr/local/bin/cloudflared \
    && chmod +x /usr/local/bin/cloudflared

WORKDIR /app

# Next.js standalone (PC에서 미리 빌드됨)
COPY dashboard-next/ ./dashboard-next/
COPY docker/tunnel.sh ./docker/tunnel.sh

RUN mkdir -p /app/data /app/logs

# CRLF 제거 + 실행 권한
RUN sed -i 's/\r$//' /app/docker/tunnel.sh \
    && chmod +x /app/docker/tunnel.sh

EXPOSE 3000

# Next.js + Cloudflare 터널 시작
CMD ["sh", "-c", "/app/docker/tunnel.sh & cd /app/dashboard-next && node server.js"]
