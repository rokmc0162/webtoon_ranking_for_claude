"""
unified_works 마이그레이션 스크립트

1. unified_works 테이블 생성
2. works 테이블에 unified_work_id FK 컬럼 추가
3. 기존 works 데이터를 title_kr 기준으로 그룹핑 → unified_works에 병합 삽입
4. works.unified_work_id 연결
"""

import psycopg2
import os
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
load_dotenv(project_root / '.env')

DATABASE_URL = os.environ.get('SUPABASE_DB_URL', '')


def run():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cursor = conn.cursor()

    # ──────────────────────────────────────
    # Step 1: unified_works 테이블 생성
    # ──────────────────────────────────────
    print("📦 Step 1: unified_works 테이블 생성...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS unified_works (
            id SERIAL PRIMARY KEY,
            title_kr TEXT NOT NULL UNIQUE,
            title_canonical TEXT,
            author TEXT DEFAULT '',
            artist TEXT DEFAULT '',
            publisher TEXT DEFAULT '',
            genre TEXT DEFAULT '',
            genre_kr TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            description TEXT DEFAULT '',
            is_riverse BOOLEAN DEFAULT FALSE,
            thumbnail_url TEXT DEFAULT '',
            thumbnail_base64 TEXT DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_unified_title_kr ON unified_works(title_kr)')
    conn.commit()
    print("  ✅ unified_works 테이블 생성 완료")

    # ──────────────────────────────────────
    # Step 2: works에 unified_work_id 컬럼 추가
    # ──────────────────────────────────────
    print("📦 Step 2: works.unified_work_id 컬럼 추가...")
    cursor.execute('''
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'works' AND column_name = 'unified_work_id'
    ''')
    if cursor.fetchone() is None:
        cursor.execute('ALTER TABLE works ADD COLUMN unified_work_id INTEGER REFERENCES unified_works(id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_works_unified ON works(unified_work_id)')
        conn.commit()
        print("  ✅ unified_work_id 컬럼 추가 완료")
    else:
        print("  ⏭️  이미 존재함, 스킵")

    # ──────────────────────────────────────
    # Step 3: 기존 works에서 title_kr 기준 그룹핑 → unified_works 삽입
    # ──────────────────────────────────────
    print("📦 Step 3: 기존 works → unified_works 마이그레이션...")

    # title_kr이 있는 모든 works 조회
    cursor.execute('''
        SELECT platform, title, title_kr, author, publisher, genre, genre_kr,
               tags, description, is_riverse, thumbnail_url, thumbnail_base64
        FROM works
        WHERE title_kr IS NOT NULL AND title_kr != ''
        ORDER BY
            CASE WHEN description IS NOT NULL AND description != '' THEN 0 ELSE 1 END,
            CASE WHEN author IS NOT NULL AND author != '' THEN 0 ELSE 1 END,
            platform
    ''')
    rows = cursor.fetchall()
    print(f"  📊 title_kr 보유 작품: {len(rows)}행")

    # title_kr 기준으로 그룹핑
    groups = {}
    for row in rows:
        (platform, title, title_kr, author, publisher, genre, genre_kr,
         tags, description, is_riverse, thumbnail_url, thumbnail_base64) = row

        if title_kr not in groups:
            groups[title_kr] = []
        groups[title_kr].append({
            'platform': platform,
            'title': title,
            'author': author or '',
            'publisher': publisher or '',
            'genre': genre or '',
            'genre_kr': genre_kr or '',
            'tags': tags or '',
            'description': description or '',
            'is_riverse': is_riverse or False,
            'thumbnail_url': thumbnail_url or '',
            'thumbnail_base64': thumbnail_base64 or '',
        })

    print(f"  📊 고유 title_kr 그룹: {len(groups)}개")

    # 병합 후 INSERT
    inserted = 0
    for title_kr, works_list in groups.items():
        # 병합 전략 적용
        merged = merge_works(title_kr, works_list)

        cursor.execute('''
            INSERT INTO unified_works
                (title_kr, title_canonical, author, artist, publisher,
                 genre, genre_kr, tags, description, is_riverse,
                 thumbnail_url, thumbnail_base64)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (title_kr) DO UPDATE SET
                title_canonical = COALESCE(NULLIF(EXCLUDED.title_canonical, ''), unified_works.title_canonical),
                author = COALESCE(NULLIF(EXCLUDED.author, ''), unified_works.author),
                publisher = COALESCE(NULLIF(EXCLUDED.publisher, ''), unified_works.publisher),
                genre = COALESCE(NULLIF(EXCLUDED.genre, ''), unified_works.genre),
                genre_kr = COALESCE(NULLIF(EXCLUDED.genre_kr, ''), unified_works.genre_kr),
                tags = CASE WHEN length(EXCLUDED.tags) > length(COALESCE(unified_works.tags, ''))
                       THEN EXCLUDED.tags ELSE unified_works.tags END,
                description = CASE WHEN length(EXCLUDED.description) > length(COALESCE(unified_works.description, ''))
                              THEN EXCLUDED.description ELSE unified_works.description END,
                is_riverse = EXCLUDED.is_riverse OR unified_works.is_riverse,
                thumbnail_url = COALESCE(NULLIF(EXCLUDED.thumbnail_url, ''), unified_works.thumbnail_url),
                thumbnail_base64 = COALESCE(NULLIF(EXCLUDED.thumbnail_base64, ''), unified_works.thumbnail_base64),
                updated_at = NOW()
        ''', (
            title_kr,
            merged['title_canonical'],
            merged['author'],
            '',  # artist (아직 수집 안함)
            merged['publisher'],
            merged['genre'],
            merged['genre_kr'],
            merged['tags'],
            merged['description'],
            merged['is_riverse'],
            merged['thumbnail_url'],
            merged['thumbnail_base64'],
        ))
        inserted += 1

    conn.commit()
    print(f"  ✅ unified_works에 {inserted}개 작품 삽입 완료")

    # ──────────────────────────────────────
    # Step 4: works.unified_work_id 연결
    # ──────────────────────────────────────
    print("📦 Step 4: works.unified_work_id 연결...")
    cursor.execute('''
        UPDATE works w
        SET unified_work_id = uw.id
        FROM unified_works uw
        WHERE w.title_kr = uw.title_kr
          AND w.title_kr IS NOT NULL AND w.title_kr != ''
          AND w.unified_work_id IS NULL
    ''')
    linked = cursor.rowcount
    conn.commit()
    print(f"  ✅ {linked}개 works 행 연결 완료")

    # ──────────────────────────────────────
    # 검증
    # ──────────────────────────────────────
    print("\n📊 검증:")
    cursor.execute('SELECT COUNT(*) FROM unified_works')
    total_unified = cursor.fetchone()[0]
    print(f"  unified_works 총 행: {total_unified}")

    cursor.execute('SELECT COUNT(*) FROM works WHERE unified_work_id IS NOT NULL')
    linked_works = cursor.fetchone()[0]
    print(f"  연결된 works 행: {linked_works}")

    cursor.execute('SELECT COUNT(*) FROM works WHERE unified_work_id IS NULL AND title_kr IS NOT NULL AND title_kr != \'\'')
    unlinked = cursor.fetchone()[0]
    print(f"  미연결 (title_kr 있지만 미연결): {unlinked}")

    # 멀티 플랫폼 작품 수
    cursor.execute('''
        SELECT COUNT(*) FROM (
            SELECT unified_work_id FROM works
            WHERE unified_work_id IS NOT NULL
            GROUP BY unified_work_id
            HAVING COUNT(DISTINCT platform) > 1
        ) sub
    ''')
    multi_platform = cursor.fetchone()[0]
    print(f"  멀티 플랫폼 작품: {multi_platform}개")

    # 나노마신 테스트
    cursor.execute("SELECT id, title_kr, title_canonical, author, genre_kr FROM unified_works WHERE title_kr = '나노마신'")
    nano = cursor.fetchone()
    if nano:
        print(f"\n  🧪 나노마신 테스트:")
        print(f"     id={nano[0]}, title_kr={nano[1]}, canonical={nano[2]}, author={nano[3]}, genre_kr={nano[4]}")
        cursor.execute('''
            SELECT platform, title FROM works WHERE unified_work_id = %s ORDER BY platform
        ''', (nano[0],))
        platforms = cursor.fetchall()
        for p in platforms:
            print(f"     - {p[0]}: {p[1]}")

    conn.close()
    print("\n✅ 마이그레이션 완료!")


def merge_works(title_kr: str, works_list: list) -> dict:
    """여러 플랫폼의 works 정보를 하나로 병합"""

    # 대표 제목: 첫 번째 일본어 플랫폼 제목 우선
    title_canonical = ''
    for w in works_list:
        if w['title'] and not title_canonical:
            title_canonical = w['title']

    # author: 빈 문자열 아닌 첫 번째 값
    author = ''
    for w in works_list:
        if w['author']:
            author = w['author']
            break

    # publisher: 빈 문자열 아닌 첫 번째 값
    publisher = ''
    for w in works_list:
        if w['publisher']:
            publisher = w['publisher']
            break

    # genre / genre_kr: 빈 문자열 아닌 첫 번째 값
    genre = ''
    genre_kr = ''
    for w in works_list:
        if w['genre'] and not genre:
            genre = w['genre']
        if w['genre_kr'] and not genre_kr:
            genre_kr = w['genre_kr']

    # description: 가장 긴 값
    description = ''
    for w in works_list:
        if len(w['description']) > len(description):
            description = w['description']

    # tags: 합집합 (쉼표 구분, 중복 제거)
    tag_set = set()
    for w in works_list:
        if w['tags']:
            for t in w['tags'].split(','):
                t = t.strip()
                if t:
                    tag_set.add(t)
    tags = ', '.join(sorted(tag_set))

    # is_riverse: OR
    is_riverse = any(w['is_riverse'] for w in works_list)

    # thumbnail: 빈 문자열 아닌 첫 번째 값
    thumbnail_url = ''
    thumbnail_base64 = ''
    for w in works_list:
        if w['thumbnail_url'] and not thumbnail_url:
            thumbnail_url = w['thumbnail_url']
        if w['thumbnail_base64'] and not thumbnail_base64:
            thumbnail_base64 = w['thumbnail_base64']

    return {
        'title_canonical': title_canonical,
        'author': author,
        'publisher': publisher,
        'genre': genre,
        'genre_kr': genre_kr,
        'tags': tags,
        'description': description,
        'is_riverse': is_riverse,
        'thumbnail_url': thumbnail_url,
        'thumbnail_base64': thumbnail_base64,
    }


if __name__ == '__main__':
    run()
