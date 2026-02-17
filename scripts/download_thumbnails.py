"""
썸네일 base64 일괄 다운로드 스크립트
- works 테이블에서 thumbnail_url이 있지만 thumbnail_base64가 없는 작품을 찾아
- 이미지를 다운로드하여 base64로 변환 후 DB에 저장
"""

import psycopg2
import base64
import urllib.request
import ssl
import time
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
import os

load_dotenv(project_root / '.env')
DATABASE_URL = os.environ.get('SUPABASE_DB_URL', '')

# SSL 검증 무시 (일부 CDN에서 필요)
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def get_pending_works():
    """base64가 없는 작품 목록 조회"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT platform, title, thumbnail_url
        FROM works
        WHERE thumbnail_url IS NOT NULL AND thumbnail_url != ''
          AND (thumbnail_base64 IS NULL OR thumbnail_base64 = '')
        ORDER BY platform, title
    """)
    rows = [{'platform': r[0], 'title': r[1], 'thumbnail_url': r[2]} for r in cursor.fetchall()]
    conn.close()
    return rows


def download_image(url: str, timeout: int = 15) -> str | None:
    """이미지 URL을 다운로드하여 base64 data URI로 변환"""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Referer': '',
        })
        resp = urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx)
        data = resp.read()

        if len(data) < 100:  # 너무 작으면 실패로 간주
            return None

        content_type = resp.headers.get('Content-Type', 'image/jpeg')
        if not content_type.startswith('image/'):
            content_type = 'image/jpeg'

        b64 = base64.b64encode(data).decode('ascii')
        return f"data:{content_type};base64,{b64}"

    except Exception as e:
        return None


def save_base64(platform: str, title: str, b64_data: str):
    """DB에 base64 저장"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE works SET thumbnail_base64 = %s, updated_at = NOW()
        WHERE platform = %s AND title = %s
    """, (b64_data, platform, title))
    conn.commit()
    conn.close()


def main():
    print("\n🖼️  썸네일 base64 일괄 다운로드 시작\n")

    pending = get_pending_works()
    total = len(pending)

    if total == 0:
        print("✅ 모든 작품에 base64 썸네일이 이미 저장되어 있습니다.")
        return

    print(f"다운로드 대상: {total}개\n")

    # 플랫폼별 통계
    platforms = {}
    for w in pending:
        p = w['platform']
        platforms[p] = platforms.get(p, 0) + 1
    for p, c in sorted(platforms.items()):
        print(f"  {p}: {c}개")
    print()

    success = 0
    failed = 0
    failed_list = []

    for i, work in enumerate(pending, 1):
        platform = work['platform']
        title = work['title']
        url = work['thumbnail_url']

        # 진행률 표시
        if i % 50 == 0 or i == 1:
            print(f"[{i}/{total}] 진행 중... (성공: {success}, 실패: {failed})")

        b64 = download_image(url)
        if b64:
            save_base64(platform, title, b64)
            success += 1
        else:
            failed += 1
            failed_list.append(f"  {platform}: {title[:40]}")

        # 레이트 리밋 (CDN 부하 방지)
        if i % 10 == 0:
            time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"완료! 성공: {success}/{total}, 실패: {failed}")

    if failed_list:
        print(f"\n실패 목록 (상위 20개):")
        for item in failed_list[:20]:
            print(item)
        if len(failed_list) > 20:
            print(f"  ... 외 {len(failed_list)-20}개")

    # 최종 검증
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT platform,
               COUNT(*) as total,
               SUM(CASE WHEN thumbnail_base64 IS NOT NULL AND thumbnail_base64 != '' THEN 1 ELSE 0 END) as has_b64
        FROM works
        WHERE thumbnail_url IS NOT NULL AND thumbnail_url != ''
        GROUP BY platform ORDER BY platform
    """)
    print(f"\n📊 플랫폼별 base64 현황:")
    for row in cursor.fetchall():
        pct = (row[2] / row[1] * 100) if row[1] > 0 else 0
        print(f"  {row[0]}: {row[2]}/{row[1]} ({pct:.0f}%)")
    conn.close()


if __name__ == "__main__":
    main()
