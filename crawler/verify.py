"""
크롤링 결과 검증 + 자동 보정 스크립트

크롤링 후 실행하여 데이터 품질을 점검하고, 가능한 부분을 자동 보정합니다:
1. 한국어 제목 매핑률 → 빈칸 자동 보정
2. 리버스 작품 감지 현황
3. 썸네일 수집 현황 (URL 존재 여부)
4. 장르 데이터 현황
5. 데이터 이상 탐지 (빈 제목, 중복 등)

실행:
    python crawler/verify.py              # 최신 날짜 검증
    python crawler/verify.py 2026-02-17   # 특정 날짜 검증
"""

import psycopg2
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / '.env')

DATABASE_URL = os.environ.get('SUPABASE_DB_URL', '')

PLATFORMS = {
    'piccoma': '픽코마',
    'linemanga': '라인망가',
    'mechacomic': '메챠코믹',
    'cmoa': '코믹시모아',
}


def _load_all_mappings():
    """리버스 + 일반 한국어 매핑 합치기"""
    all_maps = {}

    try:
        with open(project_root / 'data' / 'title_mappings.json', 'r', encoding='utf-8') as f:
            all_maps.update(json.load(f))
    except Exception:
        pass

    try:
        with open(project_root / 'data' / 'riverse_titles.json', 'r', encoding='utf-8') as f:
            all_maps.update(json.load(f))  # riverse 우선
    except Exception:
        pass

    return all_maps


def _find_korean_title(title: str, all_maps: dict) -> str:
    """제목 매핑 찾기 (직접/대괄호제거/부분매칭)"""
    if title in all_maps:
        return all_maps[title]

    # 대괄호 제거 매칭
    cleaned = title
    for b in ['【', '】', '[', ']', '(', ')']:
        cleaned = cleaned.replace(b, '')
    if cleaned != title and cleaned in all_maps:
        return all_maps[cleaned]

    # 부분 매칭 (4글자 이상)
    if len(title) >= 4:
        for jp, kr in all_maps.items():
            if len(jp) >= 4 and jp in title:
                return kr

    return ""


def fix_blank_korean_titles(conn):
    """빈칸 한국어 제목 자동 보정"""
    all_maps = _load_all_mappings()
    if not all_maps:
        return 0

    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT title FROM rankings
        WHERE (title_kr IS NULL OR title_kr = '')
    """)
    blank_titles = [r[0] for r in cur.fetchall()]

    updated = 0
    for title in blank_titles:
        kr = _find_korean_title(title, all_maps)
        if kr:
            cur.execute(
                "UPDATE rankings SET title_kr = %s WHERE title = %s AND (title_kr IS NULL OR title_kr = '')",
                (kr, title)
            )
            updated += cur.rowcount

    conn.commit()
    return updated


def verify(target_date: str = None):
    """크롤링 결과 검증 + 자동 보정"""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # 대상 날짜 결정
    if not target_date:
        cursor.execute('SELECT MAX(date) FROM rankings')
        row = cursor.fetchone()
        if not row or not row[0]:
            print("❌ DB에 데이터가 없습니다.")
            conn.close()
            return False
        target_date = row[0]

    # === 자동 보정 ===
    fixed_kr = fix_blank_korean_titles(conn)
    if fixed_kr > 0:
        print(f"🔧 한국어 제목 {fixed_kr}건 자동 보정됨")

    print("=" * 70)
    print(f"📋 크롤링 결과 검증 — {target_date}")
    print("=" * 70)

    all_ok = True
    issues = []

    for pid, pname in PLATFORMS.items():
        print(f"\n{'─' * 50}")
        print(f"📱 {pname} ({pid})")
        print(f"{'─' * 50}")

        # === 기본 통계 (종합 카테고리) ===
        cursor.execute('''
            SELECT COUNT(*),
                   SUM(CASE WHEN title_kr IS NOT NULL AND title_kr != '' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN is_riverse = TRUE THEN 1 ELSE 0 END)
            FROM rankings
            WHERE date = %s AND platform = %s AND COALESCE(sub_category, '') = ''
        ''', (target_date, pid))
        row = cursor.fetchone()
        total, kr_count, riverse_count = row[0], row[1] or 0, row[2] or 0

        if total == 0:
            print(f"  ⚠️  데이터 없음 (크롤링 실패 또는 미실행)")
            issues.append(f"{pname}: 데이터 없음")
            all_ok = False
            continue

        kr_pct = (kr_count / total) * 100
        print(f"  총 작품 수:     {total}개")
        print(f"  한국어 제목:    {kr_count}/{total} ({kr_pct:.0f}%)", end="")
        if kr_pct < 80:
            print(f" ⚠️  매핑률 낮음")
            issues.append(f"{pname}: 한국어 제목 {kr_pct:.0f}%")
        else:
            print(f" ✅")

        print(f"  리버스 작품:    {riverse_count}개", end="")
        if riverse_count == 0:
            print(" (감지된 작품 없음)")
        else:
            print(f" ✅")

        # === 썸네일 현황 ===
        # 종합 카테고리 기준으로 works 매칭 확인
        cursor.execute('''
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN w.thumbnail_url IS NOT NULL AND w.thumbnail_url != '' THEN 1 END) as has_url
            FROM rankings r
            LEFT JOIN works w ON r.platform = w.platform AND r.title = w.title
            WHERE r.date = %s AND r.platform = %s AND COALESCE(r.sub_category, '') = ''
        ''', (target_date, pid))
        t_row = cursor.fetchone()
        t_total, t_url = t_row

        print(f"  썸네일 (종합):  {t_url}/{t_total}", end="")
        if t_url < t_total:
            missing_thumbs = t_total - t_url
            print(f" ⚠️  {missing_thumbs}개 누락")
            issues.append(f"{pname}: 썸네일 {missing_thumbs}개 누락")
        else:
            print(f" ✅")

        # === 서브카테고리별 썸네일 현황 ===
        cursor.execute('''
            SELECT COALESCE(r.sub_category, '') as sub_cat,
                   COUNT(*) as total,
                   COUNT(CASE WHEN w.thumbnail_url IS NOT NULL AND w.thumbnail_url != '' THEN 1 END) as has_url
            FROM rankings r
            LEFT JOIN works w ON r.platform = w.platform AND r.title = w.title
            WHERE r.date = %s AND r.platform = %s AND r.sub_category != ''
            GROUP BY COALESCE(r.sub_category, '')
            ORDER BY sub_cat
        ''', (target_date, pid))
        sub_rows = cursor.fetchall()
        sub_missing = [(s, t, u) for s, t, u in sub_rows if u < t]
        if sub_missing:
            print(f"  ┌─ 썸네일 누락 장르:")
            for sub, t, u in sub_missing:
                print(f"  │  [{sub}] {u}/{t} ({t-u}개 누락)")
            print(f"  └─")

        # === 장르 데이터 현황 ===
        cursor.execute('''
            SELECT COUNT(*),
                   COUNT(CASE WHEN genre IS NOT NULL AND genre != '' THEN 1 END),
                   COUNT(CASE WHEN genre_kr IS NOT NULL AND genre_kr != '' THEN 1 END)
            FROM rankings
            WHERE date = %s AND platform = %s AND COALESCE(sub_category, '') = ''
        ''', (target_date, pid))
        g_row = cursor.fetchone()
        g_total, g_jp, g_kr = g_row
        print(f"  장르 (일본어):  {g_jp}/{g_total}", end="")
        if g_jp < g_total:
            print(f" ⚠️  {g_total - g_jp}개 누락")
        else:
            print(f" ✅")
        print(f"  장르 (한국어):  {g_kr}/{g_total}", end="")
        if g_kr < g_total:
            print(f" ⚠️  {g_total - g_kr}개 누락")
        else:
            print(f" ✅")

        # === 한국어 제목 빈칸 목록 ===
        cursor.execute('''
            SELECT rank, title FROM rankings
            WHERE date = %s AND platform = %s AND COALESCE(sub_category, '') = ''
              AND (title_kr IS NULL OR title_kr = '')
            ORDER BY rank LIMIT 10
        ''', (target_date, pid))
        missing = cursor.fetchall()
        if missing:
            print(f"  ┌─ 한국어 제목 빈칸 (상위 {len(missing)}개):")
            for r in missing:
                print(f"  │  {r[0]:3d}위: {r[1][:50]}")
            print(f"  └─")

        # === 리버스 작품 목록 ===
        if riverse_count > 0:
            cursor.execute('''
                SELECT rank, title, title_kr FROM rankings
                WHERE date = %s AND platform = %s AND is_riverse = TRUE
                  AND COALESCE(sub_category, '') = ''
                ORDER BY rank
            ''', (target_date, pid))
            rv_list = cursor.fetchall()
            print(f"  ┌─ 리버스 작품 목록:")
            for r in rv_list[:10]:
                kr = f" ({r[2]})" if r[2] else ""
                print(f"  │  {r[0]:3d}위: {r[1][:40]}{kr}")
            if len(rv_list) > 10:
                print(f"  │  ... 외 {len(rv_list)-10}개")
            print(f"  └─")

        # === 이상 탐지 ===
        cursor.execute('''
            SELECT COUNT(*) FROM rankings
            WHERE date = %s AND platform = %s AND (title IS NULL OR title = '')
        ''', (target_date, pid))
        empty_titles = cursor.fetchone()[0]
        if empty_titles > 0:
            print(f"  ❌ 빈 제목 {empty_titles}건!")
            issues.append(f"{pname}: 빈 제목 {empty_titles}건")
            all_ok = False

        cursor.execute('''
            SELECT COUNT(*) FROM rankings
            WHERE date = %s AND platform = %s AND (url IS NULL OR url = '')
        ''', (target_date, pid))
        empty_urls = cursor.fetchone()[0]
        if empty_urls > 0:
            print(f"  ⚠️  URL 없음 {empty_urls}건")

    # === 전체 요약 ===
    print(f"\n{'=' * 70}")
    cursor.execute('''
        SELECT COUNT(*), COUNT(DISTINCT platform) FROM rankings WHERE date = %s
    ''', (target_date,))
    total_row = cursor.fetchone()
    print(f"📊 총 {total_row[0]}개 작품, {total_row[1]}개 플랫폼")

    if issues:
        print(f"\n⚠️  발견된 이슈 ({len(issues)}건):")
        for issue in issues:
            print(f"  - {issue}")

    if all_ok and not issues:
        print("✅ 검증 통과 — 이상 없음")
    elif all_ok:
        print("⚠️  경미한 이슈 있음 (위 참조)")
    else:
        print("❌ 심각한 이슈 발견 (위 참조)")

    print("=" * 70)
    conn.close()
    return all_ok


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    verify(target)
