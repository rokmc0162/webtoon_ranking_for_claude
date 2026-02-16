#!/bin/bash
# 맥북 잠자기 방지 스크립트
# caffeinate를 사용하여 시스템이 잠들지 않도록 유지
# 크롤러 24시간 운영을 위해 필요

PIDFILE="/tmp/webtoon_caffeinate.pid"

case "$1" in
    start)
        if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
            echo "이미 실행 중입니다 (PID: $(cat $PIDFILE))"
            exit 0
        fi
        # -s: 전원 연결 시에도 잠자기 방지
        # -i: 유휴 상태에서도 잠자기 방지
        # -d: 디스플레이 잠자기 방지는 하지 않음 (화면만 꺼짐)
        caffeinate -s -i &
        echo $! > "$PIDFILE"
        echo "잠자기 방지 시작 (PID: $(cat $PIDFILE))"
        echo "디스플레이는 자동으로 꺼지지만 시스템은 계속 동작합니다."
        ;;
    stop)
        if [ -f "$PIDFILE" ]; then
            kill $(cat "$PIDFILE") 2>/dev/null
            rm -f "$PIDFILE"
            echo "잠자기 방지 중지"
        else
            echo "실행 중인 프로세스 없음"
        fi
        ;;
    status)
        if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
            echo "실행 중 (PID: $(cat $PIDFILE))"
        else
            echo "중지됨"
            rm -f "$PIDFILE" 2>/dev/null
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac
