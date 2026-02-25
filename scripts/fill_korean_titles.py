"""
한국어 제목 빈칸 채우기 스크립트

rankings 테이블에서 title_kr이 비어있는 작품을 찾아서:
1. 같은 작품이 다른 행(날짜/플랫폼)에서 title_kr을 가지고 있으면 복사
2. title_mappings.json + riverse_titles.json에서 매핑 시도
3. 매핑 안 된 작품 목록을 출력하여 수동 확인 가능

사용법:
    python3 scripts/fill_korean_titles.py              # 현황 확인
    python3 scripts/fill_korean_titles.py --update      # DB 업데이트
    python3 scripts/fill_korean_titles.py --missing      # 매핑 안 된 목록 출력
"""

import sys
import os
import json
import argparse
from pathlib import Path

# 프로젝트 루트
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / '.env')

import psycopg2

DATABASE_URL = os.environ.get('SUPABASE_DB_URL', '')


def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


def load_mappings():
    """모든 매핑 파일 로드"""
    mappings = {}

    # riverse_titles.json
    try:
        with open(project_root / 'data' / 'riverse_titles.json', 'r', encoding='utf-8') as f:
            riverse = json.load(f)
            mappings.update(riverse)
            print(f"✅ 리버스 작품 매핑: {len(riverse)}개")
    except FileNotFoundError:
        print("⚠️  riverse_titles.json 없음")

    # title_mappings.json
    try:
        with open(project_root / 'data' / 'title_mappings.json', 'r', encoding='utf-8') as f:
            title_maps = json.load(f)
            mappings.update(title_maps)
            print(f"✅ 제목 매핑: {len(title_maps)}개")
    except FileNotFoundError:
        print("⚠️  title_mappings.json 없음")

    print(f"📚 총 매핑: {len(mappings)}개")
    return mappings


def find_korean_title(jp_title, mappings):
    """일본어 제목에서 한국어 제목 찾기"""
    if not jp_title:
        return ""

    # 1. 정확한 매칭
    if jp_title in mappings:
        return mappings[jp_title]

    # 2. 대괄호 제거 후 매칭
    cleaned = jp_title
    for bracket in ['【', '】', '[', ']', '(', ')', '（', '）']:
        cleaned = cleaned.replace(bracket, '')
    cleaned = cleaned.strip()

    if cleaned != jp_title and cleaned in mappings:
        return mappings[cleaned]

    # 3. 부분 매칭 (4글자 이상)
    if len(jp_title) >= 4:
        for jp, kr in mappings.items():
            if len(jp) >= 4 and jp in jp_title:
                return kr

    return ""


def fill_from_existing_db():
    """
    DB 내에서 같은 title이 다른 행에서 title_kr을 가지고 있으면 복사
    (다른 날짜, 다른 플랫폼에서 이미 매핑된 경우)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. 같은 title이 다른 행에서 title_kr을 가지고 있는 경우
    cursor.execute("""
        UPDATE rankings r
        SET title_kr = sub.title_kr
        FROM (
            SELECT DISTINCT ON (title) title, title_kr
            FROM rankings
            WHERE title_kr IS NOT NULL AND title_kr != ''
            ORDER BY title, date DESC
        ) sub
        WHERE r.title = sub.title
          AND (r.title_kr IS NULL OR r.title_kr = '')
    """)
    cross_date_count = cursor.rowcount

    conn.commit()
    conn.close()
    return cross_date_count


def get_empty_title_kr_rankings():
    """title_kr이 비어있는 랭킹 작품 조회 (최신 날짜, 종합)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT r.platform, r.title, MIN(r.rank) as min_rank
        FROM rankings r
        WHERE r.date = (SELECT MAX(date) FROM rankings)
          AND COALESCE(r.sub_category, '') = ''
          AND (r.title_kr IS NULL OR r.title_kr = '')
        GROUP BY r.platform, r.title
        ORDER BY r.platform, min_rank
    """)

    results = cursor.fetchall()
    conn.close()
    return results


def update_title_kr_in_db(updates):
    """DB에 한국어 제목 업데이트"""
    if not updates:
        print("업데이트할 항목이 없습니다.")
        return 0

    conn = get_db_connection()
    cursor = conn.cursor()

    updated = 0
    for jp_title, kr_title in updates:
        try:
            cursor.execute("""
                UPDATE rankings
                SET title_kr = %s
                WHERE title = %s AND (title_kr IS NULL OR title_kr = '')
            """, (kr_title, jp_title))
            rows = cursor.rowcount

            if rows > 0:
                updated += 1
        except Exception as e:
            print(f"  ❌ {jp_title}: {e}")

    conn.commit()
    conn.close()
    return updated


def main():
    parser = argparse.ArgumentParser(description='한국어 제목 빈칸 채우기')
    parser.add_argument('--update', action='store_true', help='DB에 매핑된 제목 반영')
    parser.add_argument('--missing', action='store_true', help='매핑 안 된 작품 목록 출력')
    args = parser.parse_args()

    print("=" * 60)
    print("한국어 제목 빈칸 채우기")
    print("=" * 60)

    # Step 1: DB 내 크로스 참조로 채우기
    print("\n🔄 Step 1: DB 내 크로스 참조로 채우기...")
    cross_count = fill_from_existing_db()
    print(f"   ✅ DB 내 크로스 참조로 {cross_count}행 업데이트")

    # Step 2: 매핑 파일에서 찾기
    print("\n🔄 Step 2: 매핑 파일에서 찾기...")
    mappings = load_mappings()

    # 비어있는 작품 조회
    empty_titles = get_empty_title_kr_rankings()
    print(f"\n📊 최신 랭킹에서 아직 title_kr 비어있는 작품: {len(empty_titles)}개")

    if not empty_titles:
        print("✅ 모든 작품에 한국어 제목이 있습니다!")
        return

    # 매핑 시도
    can_map = []
    cannot_map = []

    seen_titles = set()
    for platform, title, rank in empty_titles:
        if title in seen_titles:
            continue
        seen_titles.add(title)

        kr = find_korean_title(title, mappings)
        if kr:
            can_map.append((title, kr))
        else:
            cannot_map.append((platform, title, rank))

    print(f"\n✅ 매핑 가능: {len(can_map)}개")
    print(f"❌ 매핑 불가 (일본 오리지널): {len(cannot_map)}개")

    # 매핑 가능 목록 출력
    if can_map:
        print(f"\n--- 매핑 가능 작품 (상위 20개) ---")
        for jp, kr in can_map[:20]:
            print(f"  {jp} → {kr}")
        if len(can_map) > 20:
            print(f"  ... 외 {len(can_map) - 20}개")

    # DB 업데이트
    if args.update and can_map:
        print(f"\n🔄 매핑 파일 기반 DB 업데이트 중...")
        updated = update_title_kr_in_db(can_map)
        print(f"💾 {updated}개 작품의 한국어 제목 업데이트 완료")

    # 매핑 불가 목록 출력
    if args.missing and cannot_map:
        print(f"\n--- 매핑 불가 작품 (플랫폼별) ---")
        by_platform = {}
        for platform, title, rank in cannot_map:
            if platform not in by_platform:
                by_platform[platform] = []
            by_platform[platform].append((title, rank))

        for platform, titles in sorted(by_platform.items()):
            print(f"\n  [{platform}] ({len(titles)}개)")
            for title, rank in titles[:20]:
                print(f"    {rank:3d}위: {title}")
            if len(titles) > 20:
                print(f"    ... 외 {len(titles) - 20}개")

    # 요약
    total_empty = len(empty_titles)
    total_unique = len(seen_titles)
    filled = len(can_map)
    remaining = len(cannot_map)

    print(f"\n{'=' * 60}")
    print(f"📊 요약:")
    print(f"   비어있는 작품 (종합 랭킹): {total_empty}개 ({total_unique}개 고유)")
    print(f"   매핑 가능: {filled}개")
    print(f"   매핑 불가 (일본 오리지널): {remaining}개")
    if not args.update and can_map:
        print(f"\n   💡 --update 옵션으로 매핑 가능한 {filled}개를 DB에 반영할 수 있습니다")
    print("=" * 60)


if __name__ == "__main__":
    main()
