"""
DB 마이그레이션: works 테이블 확장 + reviews 테이블 생성
- works: author, publisher, label, tags, description, hearts, favorites, rating, review_count, detail_scraped_at
- reviews: 플랫폼별 리뷰/코멘트 저장
"""

import psycopg2
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


def step1_add_work_columns():
    """works 테이블에 상세 메타데이터 컬럼 추가"""
    print("=" * 60)
    print("Step 1: works 테이블 컬럼 추가")
    print("=" * 60)

    conn = get_conn()
    cursor = conn.cursor()

    columns = [
        ("author", "VARCHAR(500) DEFAULT ''"),
        ("publisher", "VARCHAR(500) DEFAULT ''"),
        ("label", "VARCHAR(500) DEFAULT ''"),
        ("tags", "TEXT DEFAULT ''"),
        ("description", "TEXT DEFAULT ''"),
        ("hearts", "INTEGER"),
        ("favorites", "INTEGER"),
        ("rating", "DECIMAL(3,2)"),
        ("review_count", "INTEGER"),
        ("detail_scraped_at", "TIMESTAMPTZ"),
    ]

    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE works ADD COLUMN {col_name} {col_type}")
            print(f"  + {col_name} ({col_type})")
        except psycopg2.errors.DuplicateColumn:
            conn.rollback()
            print(f"  - {col_name} (이미 존재)")

    conn.commit()
    conn.close()
    print()


def step2_create_reviews_table():
    """reviews 테이블 생성"""
    print("=" * 60)
    print("Step 2: reviews 테이블 생성")
    print("=" * 60)

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id BIGSERIAL PRIMARY KEY,
            platform VARCHAR(50) NOT NULL,
            work_title VARCHAR(500) NOT NULL,
            reviewer_name VARCHAR(200) DEFAULT '',
            reviewer_info VARCHAR(200) DEFAULT '',
            body TEXT NOT NULL,
            rating INTEGER,
            likes_count INTEGER DEFAULT 0,
            is_spoiler BOOLEAN DEFAULT FALSE,
            reviewed_at TIMESTAMPTZ,
            collected_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(platform, work_title, reviewer_name, reviewed_at)
        )
    """)
    print("  + reviews 테이블 생성됨")

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reviews_platform_work
        ON reviews(platform, work_title)
    """)
    print("  + idx_reviews_platform_work 인덱스")

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reviews_collected_at
        ON reviews(collected_at)
    """)
    print("  + idx_reviews_collected_at 인덱스")

    conn.commit()
    conn.close()
    print()


def step3_verify():
    """마이그레이션 결과 검증"""
    print("=" * 60)
    print("Step 3: 검증")
    print("=" * 60)

    conn = get_conn()
    cursor = conn.cursor()

    # works 컬럼 확인
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'works'
        ORDER BY ordinal_position
    """)
    print("\n[works 테이블 컬럼]")
    for row in cursor.fetchall():
        print(f"  {row[0]:<25} {row[1]}")

    # reviews 테이블 확인
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'reviews'
        ORDER BY ordinal_position
    """)
    cols = cursor.fetchall()
    print(f"\n[reviews 테이블 컬럼] ({len(cols)}개)")
    for row in cols:
        print(f"  {row[0]:<25} {row[1]}")

    # 통계
    cursor.execute("SELECT COUNT(*) FROM works")
    works_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM reviews")
    reviews_count = cursor.fetchone()[0]

    print(f"\nworks: {works_count}개, reviews: {reviews_count}개")

    conn.close()
    print()


if __name__ == "__main__":
    print("\n🔄 DB 마이그레이션: 상세 메타데이터 + 리뷰\n")
    step1_add_work_columns()
    step2_create_reviews_table()
    step3_verify()
    print("✅ 마이그레이션 완료!")
