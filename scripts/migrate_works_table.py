"""
works 테이블 확장 마이그레이션
- 신규 컬럼 추가: title_kr, genre_kr, is_riverse, first_seen_date, last_seen_date, best_rank
- 기존 rankings 데이터로부터 일괄 채움
"""

import psycopg2
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
import os

load_dotenv(project_root / '.env')
DATABASE_URL = os.environ.get('SUPABASE_DB_URL', '')


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def step1_add_columns():
    """works 테이블에 신규 컬럼 추가"""
    print("=" * 60)
    print("Step 1: works 테이블 컬럼 추가")
    print("=" * 60)

    conn = get_conn()
    cursor = conn.cursor()

    columns_to_add = [
        ("title_kr", "VARCHAR(500) DEFAULT ''"),
        ("genre_kr", "VARCHAR(200) DEFAULT ''"),
        ("is_riverse", "BOOLEAN DEFAULT FALSE"),
        ("first_seen_date", "DATE"),
        ("last_seen_date", "DATE"),
        ("best_rank", "INTEGER"),
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE works ADD COLUMN {col_name} {col_type}")
            print(f"  ✅ {col_name} ({col_type}) 추가됨")
        except psycopg2.errors.DuplicateColumn:
            conn.rollback()
            print(f"  ⏩ {col_name} 이미 존재함")

    conn.commit()
    conn.close()
    print()


def step2_populate_from_rankings():
    """rankings 테이블의 기존 데이터로 works 정보 채우기"""
    print("=" * 60)
    print("Step 2: rankings 데이터에서 작품 정보 추출")
    print("=" * 60)

    conn = get_conn()
    cursor = conn.cursor()

    # rankings에 있지만 works에 없는 작품 추가
    cursor.execute("""
        INSERT INTO works (platform, title, url, genre, updated_at)
        SELECT DISTINCT ON (r.platform, r.title)
            r.platform, r.title, r.url, r.genre, NOW()
        FROM rankings r
        LEFT JOIN works w ON r.platform = w.platform AND r.title = w.title
        WHERE w.title IS NULL
        ON CONFLICT (platform, title) DO NOTHING
    """)
    new_count = cursor.rowcount
    print(f"  ✅ 신규 작품 {new_count}개 추가")

    conn.commit()

    # title_kr 채우기: rankings에서 가장 최근 title_kr 가져오기
    cursor.execute("""
        UPDATE works w SET title_kr = sub.title_kr
        FROM (
            SELECT DISTINCT ON (platform, title) platform, title, title_kr
            FROM rankings
            WHERE title_kr IS NOT NULL AND title_kr != ''
            ORDER BY platform, title, date DESC
        ) sub
        WHERE w.platform = sub.platform AND w.title = sub.title
          AND (w.title_kr IS NULL OR w.title_kr = '')
    """)
    print(f"  ✅ title_kr 업데이트: {cursor.rowcount}개")

    # genre 채우기: rankings에서 가장 최근 genre 가져오기
    cursor.execute("""
        UPDATE works w SET genre = sub.genre
        FROM (
            SELECT DISTINCT ON (platform, title) platform, title, genre
            FROM rankings
            WHERE genre IS NOT NULL AND genre != ''
            ORDER BY platform, title, date DESC
        ) sub
        WHERE w.platform = sub.platform AND w.title = sub.title
          AND (w.genre IS NULL OR w.genre = '')
    """)
    print(f"  ✅ genre 업데이트: {cursor.rowcount}개")

    # genre_kr 채우기
    cursor.execute("""
        UPDATE works w SET genre_kr = sub.genre_kr
        FROM (
            SELECT DISTINCT ON (platform, title) platform, title, genre_kr
            FROM rankings
            WHERE genre_kr IS NOT NULL AND genre_kr != ''
            ORDER BY platform, title, date DESC
        ) sub
        WHERE w.platform = sub.platform AND w.title = sub.title
          AND (w.genre_kr IS NULL OR w.genre_kr = '')
    """)
    print(f"  ✅ genre_kr 업데이트: {cursor.rowcount}개")

    # is_riverse 채우기
    cursor.execute("""
        UPDATE works w SET is_riverse = TRUE
        FROM (
            SELECT DISTINCT platform, title
            FROM rankings
            WHERE is_riverse = TRUE
        ) sub
        WHERE w.platform = sub.platform AND w.title = sub.title
          AND w.is_riverse = FALSE
    """)
    print(f"  ✅ is_riverse 업데이트: {cursor.rowcount}개")

    # first_seen_date 채우기
    cursor.execute("""
        UPDATE works w SET first_seen_date = sub.first_date::date
        FROM (
            SELECT platform, title, MIN(date) as first_date
            FROM rankings
            GROUP BY platform, title
        ) sub
        WHERE w.platform = sub.platform AND w.title = sub.title
          AND w.first_seen_date IS NULL
    """)
    print(f"  ✅ first_seen_date 업데이트: {cursor.rowcount}개")

    # last_seen_date 채우기
    cursor.execute("""
        UPDATE works w SET last_seen_date = sub.last_date::date
        FROM (
            SELECT platform, title, MAX(date) as last_date
            FROM rankings
            GROUP BY platform, title
        ) sub
        WHERE w.platform = sub.platform AND w.title = sub.title
    """)
    print(f"  ✅ last_seen_date 업데이트: {cursor.rowcount}개")

    # best_rank 채우기 (종합 랭킹 기준, sub_category='')
    cursor.execute("""
        UPDATE works w SET best_rank = sub.best_rank
        FROM (
            SELECT platform, title, MIN(rank) as best_rank
            FROM rankings
            WHERE sub_category = '' OR sub_category IS NULL
            GROUP BY platform, title
        ) sub
        WHERE w.platform = sub.platform AND w.title = sub.title
    """)
    print(f"  ✅ best_rank 업데이트: {cursor.rowcount}개")

    # url 채우기 (works에 url이 없는 경우)
    cursor.execute("""
        UPDATE works w SET url = sub.url
        FROM (
            SELECT DISTINCT ON (platform, title) platform, title, url
            FROM rankings
            WHERE url IS NOT NULL AND url != ''
            ORDER BY platform, title, date DESC
        ) sub
        WHERE w.platform = sub.platform AND w.title = sub.title
          AND (w.url IS NULL OR w.url = '')
    """)
    print(f"  ✅ url 업데이트: {cursor.rowcount}개")

    conn.commit()
    conn.close()
    print()


def step3_verify():
    """결과 검증"""
    print("=" * 60)
    print("Step 3: 결과 검증")
    print("=" * 60)

    conn = get_conn()
    cursor = conn.cursor()

    # 플랫폼별 작품 수
    cursor.execute("""
        SELECT platform, COUNT(*) as total,
               SUM(CASE WHEN title_kr != '' AND title_kr IS NOT NULL THEN 1 ELSE 0 END) as has_kr,
               SUM(CASE WHEN genre != '' AND genre IS NOT NULL THEN 1 ELSE 0 END) as has_genre,
               SUM(CASE WHEN is_riverse = TRUE THEN 1 ELSE 0 END) as riverse,
               SUM(CASE WHEN thumbnail_url != '' AND thumbnail_url IS NOT NULL THEN 1 ELSE 0 END) as has_thumb,
               SUM(CASE WHEN best_rank IS NOT NULL THEN 1 ELSE 0 END) as has_best_rank,
               SUM(CASE WHEN first_seen_date IS NOT NULL THEN 1 ELSE 0 END) as has_first_seen
        FROM works
        GROUP BY platform
        ORDER BY platform
    """)

    print(f"\n{'플랫폼':<15} {'총작품':>6} {'한국어':>6} {'장르':>6} {'리버스':>6} {'썸네일':>6} {'최고순위':>8} {'첫등장':>6}")
    print("-" * 75)
    for row in cursor.fetchall():
        print(f"{row[0]:<15} {row[1]:>6} {row[2]:>6} {row[3]:>6} {row[4]:>6} {row[5]:>6} {row[6]:>8} {row[7]:>6}")

    # 전체 통계
    cursor.execute("SELECT COUNT(*) FROM works")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM works WHERE thumbnail_base64 IS NOT NULL AND thumbnail_base64 != ''")
    has_base64 = cursor.fetchone()[0]

    print(f"\n전체 작품 수: {total}")
    print(f"base64 썸네일 보유: {has_base64}")

    conn.close()
    print()


if __name__ == "__main__":
    print("\n🔄 works 테이블 마이그레이션 시작\n")
    step1_add_columns()
    step2_populate_from_rankings()
    step3_verify()
    print("✅ 마이그레이션 완료!")
