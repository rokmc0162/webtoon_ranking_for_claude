"""
Supabase PostgreSQL 데이터베이스 스키마 및 저장 로직
"""

import psycopg2
import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import sys
from dotenv import load_dotenv

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from crawler.utils import get_korean_title, is_riverse_title, translate_genre

# 환경변수 로드
load_dotenv(project_root / '.env')
DATABASE_URL = os.environ.get('SUPABASE_DB_URL', '')


def get_db_connection():
    """Supabase PostgreSQL 연결"""
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def init_db():
    """데이터베이스 연결 확인"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        conn.close()
        print(f"✅ DB 연결 확인 완료: Supabase PostgreSQL")
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")
        raise


def save_rankings(date: str, platform: str, rankings: List[Dict[str, Any]],
                   sub_category: str = ''):
    """
    랭킹 데이터 저장 (upsert 방식)

    Args:
        date: 날짜 (YYYY-MM-DD)
        platform: 플랫폼 이름 (piccoma, linemanga, mechacomic, cmoa)
        rankings: 랭킹 데이터 리스트
        sub_category: 서브 카테고리 (예: 'ファンタジー', '恋愛' 등, 기본: '' = 종합)
    """
    if not rankings:
        print(f"⚠️  {platform}: 저장할 데이터 없음")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    saved_count = 0
    for item in rankings:
        # 제목 매핑
        title_kr = get_korean_title(item['title'])

        # 장르 번역
        genre_kr = translate_genre(item.get('genre', ''))

        # 리버스 작품 여부
        is_riverse = is_riverse_title(item['title'])

        try:
            cursor.execute('''
                INSERT INTO rankings
                (date, platform, sub_category, rank, title, title_kr, genre, genre_kr, url, is_riverse)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (date, platform, sub_category, rank)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    title_kr = EXCLUDED.title_kr,
                    genre = EXCLUDED.genre,
                    genre_kr = EXCLUDED.genre_kr,
                    url = EXCLUDED.url,
                    is_riverse = EXCLUDED.is_riverse
            ''', (
                date,
                platform,
                sub_category,
                item['rank'],
                item['title'],
                title_kr,
                item.get('genre', ''),
                genre_kr,
                item.get('url', ''),
                is_riverse
            ))
            saved_count += 1
        except Exception as e:
            print(f"❌ 저장 실패 ({platform} {item['rank']}위): {e}")

    conn.commit()
    conn.close()

    print(f"💾 {platform}: {saved_count}개 작품 DB 저장")


def _upsert_unified_work(cursor, title_kr: str, title: str, author: str = '',
                          publisher: str = '', genre: str = '', genre_kr: str = '',
                          tags: str = '', description: str = '',
                          is_riverse: bool = False, thumbnail_url: str = '',
                          thumbnail_base64: str = '') -> Optional[int]:
    """
    unified_works 테이블 UPSERT 후 id 반환.
    title_kr이 비어있으면 None 반환.
    """
    if not title_kr:
        return None

    cursor.execute('''
        INSERT INTO unified_works
            (title_kr, title_canonical, author, publisher, genre, genre_kr,
             tags, description, is_riverse, thumbnail_url, thumbnail_base64)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        RETURNING id
    ''', (
        title_kr, title, author, publisher, genre, genre_kr,
        tags, description, is_riverse, thumbnail_url, thumbnail_base64
    ))
    row = cursor.fetchone()
    return row[0] if row else None


def save_works_metadata(platform: str, works: List[Dict[str, Any]],
                        date: str = '', sub_category: str = ''):
    """
    작품 메타데이터 저장/갱신 (독립 작품 DB)
    + unified_works 자동 연결

    Args:
        platform: 플랫폼 이름
        works: [{'title': str, 'thumbnail_url': str, 'url': str, 'genre': str, 'rank': int}, ...]
        date: 크롤링 날짜 (YYYY-MM-DD) — first/last_seen_date 갱신용
        sub_category: 서브 카테고리 ('' = 종합 → best_rank 갱신)
    """
    if not works:
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    count = 0
    for item in works:
        title = item.get('title', '')
        thumbnail_url = item.get('thumbnail_url', '')
        url = item.get('url', '')
        genre = item.get('genre', '')
        rank = item.get('rank', None)

        if not title:
            continue

        # 한국어 제목, 리버스 여부 계산
        title_kr = get_korean_title(title)
        genre_kr = translate_genre(genre) if genre else ''
        is_riverse = is_riverse_title(title)

        # unified_works UPSERT → id 획득
        unified_id = _upsert_unified_work(
            cursor, title_kr, title,
            genre=genre, genre_kr=genre_kr,
            is_riverse=is_riverse, thumbnail_url=thumbnail_url
        )

        # UPSERT: 신규 작품이면 INSERT, 기존이면 갱신
        cursor.execute('''
            INSERT INTO works (platform, title, thumbnail_url, url, genre, genre_kr,
                               title_kr, is_riverse, first_seen_date, last_seen_date,
                               best_rank, unified_work_id, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s != '' THEN %s::date ELSE NULL END,
                    CASE WHEN %s != '' THEN %s::date ELSE NULL END,
                    CASE WHEN %s = '' AND %s IS NOT NULL THEN %s ELSE NULL END,
                    %s, NOW())
            ON CONFLICT(platform, title)
            DO UPDATE SET
                thumbnail_url = CASE WHEN EXCLUDED.thumbnail_url != '' THEN EXCLUDED.thumbnail_url
                                     ELSE works.thumbnail_url END,
                url = CASE WHEN EXCLUDED.url != '' THEN EXCLUDED.url ELSE works.url END,
                genre = CASE WHEN EXCLUDED.genre != '' THEN EXCLUDED.genre ELSE works.genre END,
                genre_kr = CASE WHEN EXCLUDED.genre_kr != '' THEN EXCLUDED.genre_kr ELSE works.genre_kr END,
                title_kr = CASE WHEN EXCLUDED.title_kr != '' THEN EXCLUDED.title_kr ELSE works.title_kr END,
                is_riverse = EXCLUDED.is_riverse OR works.is_riverse,
                first_seen_date = LEAST(works.first_seen_date, EXCLUDED.first_seen_date),
                last_seen_date = GREATEST(works.last_seen_date, EXCLUDED.last_seen_date),
                best_rank = CASE
                    WHEN EXCLUDED.best_rank IS NOT NULL AND (works.best_rank IS NULL OR EXCLUDED.best_rank < works.best_rank)
                    THEN EXCLUDED.best_rank ELSE works.best_rank END,
                unified_work_id = COALESCE(EXCLUDED.unified_work_id, works.unified_work_id),
                updated_at = NOW()
        ''', (
            platform, title, thumbnail_url, url, genre, genre_kr,
            title_kr, is_riverse,
            date, date,   # first_seen_date
            date, date,   # last_seen_date
            sub_category, rank, rank,  # best_rank (only for 종합)
            unified_id
        ))
        count += 1

    conn.commit()
    conn.close()

    if count > 0:
        print(f"🖼️  {platform}: {count}개 작품 메타데이터 저장")


def get_works_thumbnails(platform: str) -> Dict[str, str]:
    """
    플랫폼의 모든 작품 썸네일 URL 맵 반환

    Returns:
        {title: thumbnail_url} 딕셔너리
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT title, thumbnail_url
        FROM works
        WHERE platform = %s AND thumbnail_url IS NOT NULL AND thumbnail_url != ''
    ''', (platform,))

    result = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return result


def save_thumbnail_base64(platform: str, title: str, b64_data: str):
    """
    작품 썸네일 base64 데이터 저장

    Args:
        platform: 플랫폼 이름
        title: 작품명
        b64_data: "data:image/jpeg;base64,..." 형식의 data URI
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE works SET thumbnail_base64 = %s, updated_at = NOW()
        WHERE platform = %s AND title = %s
    ''', (b64_data, platform, title))
    conn.commit()
    conn.close()


def get_thumbnails_base64(platform: str) -> Dict[str, str]:
    """
    플랫폼의 모든 작품 썸네일 base64 맵 반환

    Returns:
        {title: "data:image/...;base64,..."} 딕셔너리
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, thumbnail_base64
        FROM works
        WHERE platform = %s AND thumbnail_base64 IS NOT NULL AND thumbnail_base64 != ''
    ''', (platform,))
    result = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return result


def get_works_without_base64(platform: str) -> List[Dict[str, str]]:
    """
    base64가 없지만 thumbnail_url이 있는 작품 목록 반환

    Returns:
        [{'title': str, 'thumbnail_url': str}, ...]
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, thumbnail_url
        FROM works
        WHERE platform = %s
          AND thumbnail_url IS NOT NULL AND thumbnail_url != ''
          AND (thumbnail_base64 IS NULL OR thumbnail_base64 = '')
    ''', (platform,))
    result = [{'title': row[0], 'thumbnail_url': row[1]} for row in cursor.fetchall()]
    conn.close()
    return result


def save_work_detail(platform: str, title: str, detail: Dict[str, Any]):
    """
    작품 상세 메타데이터 저장 (상세 페이지에서 수집)
    COALESCE(NULLIF(...), existing) 패턴으로 기존 데이터 보호
    + unified_works에도 상세 정보 반영

    Args:
        platform: 플랫폼 이름
        title: 작품 제목 (일본어)
        detail: {author, publisher, label, tags, description, hearts, favorites, rating, review_count}
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE works SET
            author = COALESCE(NULLIF(%s, ''), author),
            publisher = COALESCE(NULLIF(%s, ''), publisher),
            label = COALESCE(NULLIF(%s, ''), label),
            tags = COALESCE(NULLIF(%s, ''), tags),
            description = COALESCE(NULLIF(%s, ''), description),
            hearts = COALESCE(%s, hearts),
            favorites = COALESCE(%s, favorites),
            rating = COALESCE(%s, rating),
            review_count = COALESCE(%s, review_count),
            detail_scraped_at = NOW(),
            updated_at = NOW()
        WHERE platform = %s AND title = %s
    ''', (
        detail.get('author', ''),
        detail.get('publisher', ''),
        detail.get('label', ''),
        detail.get('tags', ''),
        detail.get('description', ''),
        detail.get('hearts'),
        detail.get('favorites'),
        detail.get('rating'),
        detail.get('review_count'),
        platform, title
    ))
    updated = cursor.rowcount

    # unified_works에도 상세 정보 반영
    title_kr = get_korean_title(title)
    if title_kr:
        _upsert_unified_work(
            cursor, title_kr, title,
            author=detail.get('author', ''),
            publisher=detail.get('publisher', ''),
            tags=detail.get('tags', ''),
            description=detail.get('description', ''),
        )

    conn.commit()
    conn.close()
    return updated > 0


def save_reviews(platform: str, work_title: str, reviews: List[Dict[str, Any]]) -> int:
    """
    리뷰/코멘트 벌크 저장 (ON CONFLICT DO NOTHING으로 중복 방지)

    Args:
        platform: 플랫폼 이름
        work_title: 작품 제목 (일본어)
        reviews: [{reviewer_name, reviewer_info, body, rating, likes_count, is_spoiler, reviewed_at}]

    Returns:
        저장된 리뷰 수
    """
    if not reviews:
        return 0

    conn = get_db_connection()
    cursor = conn.cursor()
    count = 0
    for r in reviews:
        try:
            cursor.execute('''
                INSERT INTO reviews
                (platform, work_title, reviewer_name, reviewer_info, body,
                 rating, likes_count, is_spoiler, reviewed_at, collected_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (platform, work_title, reviewer_name, reviewed_at)
                DO NOTHING
            ''', (
                platform, work_title,
                r.get('reviewer_name', ''),
                r.get('reviewer_info', ''),
                r.get('body', ''),
                r.get('rating'),
                r.get('likes_count', 0),
                r.get('is_spoiler', False),
                r.get('reviewed_at')
            ))
            if cursor.rowcount > 0:
                count += 1
        except Exception as e:
            print(f"⚠️  리뷰 저장 실패: {e}")
    conn.commit()
    conn.close()
    return count


def get_works_needing_detail(max_count: int = 50, riverse_only: bool = False) -> List[Dict[str, str]]:
    """
    상세 메타데이터가 필요한 작품 목록 조회
    - detail_scraped_at이 NULL이거나 7일 이상 지난 작품
    - 최근 랭킹 등장 순으로 우선

    Args:
        max_count: 최대 작품 수
        riverse_only: True이면 리버스 작품만 (detail_scraped_at 조건 무시, 강제 재수집)

    Returns:
        [{platform, title, url}, ...]
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    if riverse_only:
        # 리버스 작품은 기존 수집 여부와 무관하게 전부 재수집
        cursor.execute('''
            SELECT platform, title, url
            FROM works
            WHERE url IS NOT NULL AND url != ''
              AND is_riverse = TRUE
              AND platform != 'asura'
            ORDER BY last_seen_date DESC NULLS LAST
            LIMIT %s
        ''', (max_count,))
    else:
        cursor.execute('''
            SELECT platform, title, url
            FROM works
            WHERE url IS NOT NULL AND url != ''
              AND (detail_scraped_at IS NULL
                   OR detail_scraped_at < NOW() - INTERVAL '7 days')
            ORDER BY last_seen_date DESC NULLS LAST,
                     detail_scraped_at ASC NULLS FIRST
            LIMIT %s
        ''', (max_count,))
    result = [{'platform': r[0], 'title': r[1], 'url': r[2]} for r in cursor.fetchall()]
    conn.close()
    return result


def get_works_for_review(max_count: int = 100, riverse_only: bool = False) -> List[Dict[str, str]]:
    """
    리뷰 수집 대상 작품 목록 (최근 7일 랭킹 등장, 픽코마 제외)
    플랫폼별 균등 분배: max_count를 플랫폼 수로 나눠서 각 플랫폼에서 고르게 가져옴

    Args:
        max_count: 최대 작품 수 (0 = 무제한)
        riverse_only: True이면 리버스 작품만 (7일 제한 해제)

    Returns:
        [{platform, title, url}, ...]
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if riverse_only:
        # 리버스 작품 전체 (날짜 제한 없이, 픽코마/아수라 제외)
        cursor.execute('''
            SELECT DISTINCT w.platform, w.title, w.url
            FROM works w
            WHERE w.is_riverse = TRUE
              AND w.platform NOT IN ('piccoma', 'asura')
              AND w.url IS NOT NULL AND w.url != ''
            ORDER BY w.platform, w.title
        ''')
    elif max_count <= 0 or max_count >= 10000:
        # 무제한: 전체 가져오기
        cursor.execute('''
            SELECT DISTINCT w.platform, w.title, w.url
            FROM works w
            WHERE w.platform != 'piccoma'
              AND w.url IS NOT NULL AND w.url != ''
              AND w.last_seen_date >= (CURRENT_DATE - INTERVAL '7 days')::date
            ORDER BY w.platform, w.title
        ''')
    else:
        # 플랫폼별 균등 분배 (WINDOW 함수 사용)
        cursor.execute('''
            SELECT platform, title, url FROM (
                SELECT w.platform, w.title, w.url,
                       ROW_NUMBER() OVER (PARTITION BY w.platform ORDER BY w.title) as rn
                FROM works w
                WHERE w.platform != 'piccoma'
                  AND w.url IS NOT NULL AND w.url != ''
                  AND w.last_seen_date >= (CURRENT_DATE - INTERVAL '7 days')::date
            ) sub
            WHERE rn <= %s
            ORDER BY platform, title
        ''', (max_count,))

    result = [{'platform': r[0], 'title': r[1], 'url': r[2]} for r in cursor.fetchall()]
    conn.close()
    return result


def get_works_genres(platform: str) -> Dict[str, str]:
    """
    플랫폼의 모든 작품 장르 캐시 맵 반환

    Returns:
        {title: genre} 딕셔너리
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, genre
        FROM works
        WHERE platform = %s AND genre IS NOT NULL AND genre != ''
    ''', (platform,))
    result = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return result


def save_work_genre(platform: str, title: str, genre: str):
    """작품 장르를 works 테이블에 캐시 저장"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE works SET genre = %s, updated_at = NOW()
        WHERE platform = %s AND title = %s
    ''', (genre, platform, title))
    if cursor.rowcount == 0:
        # works에 아직 없으면 insert
        cursor.execute('''
            INSERT INTO works (platform, title, genre, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (platform, title) DO NOTHING
        ''', (platform, title, genre))
    conn.commit()
    conn.close()


def update_rankings_genre(platform: str, title: str, genre: str, genre_kr: str):
    """rankings 테이블에서 장르가 비어있는 해당 작품 레코드를 모두 업데이트"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE rankings SET genre = %s, genre_kr = %s
        WHERE platform = %s AND title = %s AND (genre IS NULL OR genre = '')
    ''', (genre, genre_kr, platform, title))
    conn.commit()
    conn.close()


def backup_to_json(date: str, platform: str, rankings: List[Dict[str, Any]]):
    """
    JSON 백업 저장 (DB 장애 대비)

    Args:
        date: 날짜 (YYYY-MM-DD)
        platform: 플랫폼 이름
        rankings: 랭킹 데이터 리스트
    """
    backup_dir = project_root / 'data' / 'backup' / date
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_file = backup_dir / f'{platform}.json'

    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(rankings, f, ensure_ascii=False, indent=2)

    print(f"📦 {platform}: JSON 백업 완료 ({backup_file})")


def get_available_dates() -> List[str]:
    """사용 가능한 날짜 목록 반환 (최신순)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT DISTINCT date
        FROM rankings
        ORDER BY date DESC
    ''')

    dates = [row[0] for row in cursor.fetchall()]
    conn.close()

    return dates


def get_rank_history(title: str, platform: str, days: int = 30) -> List[Dict[str, Any]]:
    """
    특정 작품의 순위 히스토리 조회

    Args:
        title: 작품명 (일본어)
        platform: 플랫폼 이름
        days: 조회 일수 (기본 30일)

    Returns:
        [{'date': '2026-02-15', 'rank': 1}, ...]
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT date, rank
        FROM rankings
        WHERE title = %s AND platform = %s
        ORDER BY date DESC
        LIMIT %s
    ''', (title, platform, days))

    history = [
        {'date': row[0], 'rank': row[1]}
        for row in cursor.fetchall()
    ]

    conn.close()

    # 날짜 오름차순으로 정렬 (그래프용)
    history.reverse()

    return history


def get_previous_date(date: str, platform: str) -> Optional[str]:
    """
    특정 날짜 이전의 가장 최근 날짜 반환

    Args:
        date: 기준 날짜 (YYYY-MM-DD)
        platform: 플랫폼 이름

    Returns:
        이전 날짜 (YYYY-MM-DD) 또는 None
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT DISTINCT date
        FROM rankings
        WHERE date < %s AND platform = %s
        ORDER BY date DESC
        LIMIT 1
    ''', (date, platform))

    row = cursor.fetchone()
    conn.close()

    return row[0] if row else None


def calculate_rank_changes(date: str, platform: str) -> Dict[str, int]:
    """
    전일 대비 순위 변동 계산

    Args:
        date: 현재 날짜
        platform: 플랫폼 이름

    Returns:
        {제목: 변동값} 딕셔너리
        - 양수: 순위 상승 (예: 10위 → 5위 = +5)
        - 음수: 순위 하락
        - 999: 신규 진입 (NEW)
        - 0: 변동 없음
    """
    prev_date = get_previous_date(date, platform)
    if not prev_date:
        return {}  # 이전 데이터 없음

    conn = get_db_connection()
    cursor = conn.cursor()

    # 현재 날짜 랭킹
    cursor.execute('''
        SELECT title, rank
        FROM rankings
        WHERE date = %s AND platform = %s
    ''', (date, platform))
    current = {row[0]: row[1] for row in cursor.fetchall()}

    # 이전 날짜 랭킹
    cursor.execute('''
        SELECT title, rank
        FROM rankings
        WHERE date = %s AND platform = %s
    ''', (prev_date, platform))
    previous = {row[0]: row[1] for row in cursor.fetchall()}

    conn.close()

    # 변동 계산
    changes = {}
    for title, current_rank in current.items():
        if title in previous:
            prev_rank = previous[title]
            changes[title] = prev_rank - current_rank  # 양수 = 상승
        else:
            changes[title] = 999  # 신규 진입

    return changes


if __name__ == "__main__":
    # 연결 테스트
    init_db()
    print("\n✅ DB 연결 테스트 완료")
