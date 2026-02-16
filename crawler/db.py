"""
SQLite 데이터베이스 스키마 및 저장 로직
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import sys

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from crawler.utils import get_korean_title, is_riverse_title, translate_genre


# DB 경로
DB_PATH = project_root / 'data' / 'rankings.db'


def init_db():
    """데이터베이스 초기화 - 최초 1회 실행"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # rankings 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rankings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            platform TEXT NOT NULL,
            rank INTEGER NOT NULL,
            title TEXT NOT NULL,
            title_kr TEXT,
            genre TEXT,
            genre_kr TEXT,
            url TEXT NOT NULL,
            is_riverse BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, platform, rank)
        )
    ''')

    # 인덱스 생성
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_date_platform ON rankings(date, platform)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_riverse ON rankings(is_riverse) WHERE is_riverse = 1')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_title ON rankings(title)')

    # works 메타데이터 테이블 (썸네일 등 캐싱용)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS works (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            title TEXT NOT NULL,
            thumbnail_url TEXT,
            thumbnail_base64 TEXT,
            url TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(platform, title)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_works_platform ON works(platform)')

    # migration: 기존 works 테이블에 thumbnail_base64 컬럼이 없으면 추가
    try:
        cursor.execute('ALTER TABLE works ADD COLUMN thumbnail_base64 TEXT')
    except sqlite3.OperationalError:
        pass  # 이미 존재

    conn.commit()
    conn.close()

    print(f"✅ DB 초기화 완료: {DB_PATH}")


def save_rankings(date: str, platform: str, rankings: List[Dict[str, Any]]):
    """
    랭킹 데이터 저장 (upsert 방식)

    Args:
        date: 날짜 (YYYY-MM-DD)
        platform: 플랫폼 이름 (piccoma, linemanga, mechacomic, cmoa)
        rankings: 랭킹 데이터 리스트
            [{'rank': 1, 'title': '제목', 'genre': '장르', 'url': 'http://...', ...}, ...]
    """
    if not rankings:
        print(f"⚠️  {platform}: 저장할 데이터 없음")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    saved_count = 0
    for item in rankings:
        # 제목 매핑
        title_kr = get_korean_title(item['title'])

        # 장르 번역
        genre_kr = translate_genre(item.get('genre', ''))

        # 리버스 작품 여부
        is_riverse = 1 if is_riverse_title(item['title']) else 0

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO rankings
                (date, platform, rank, title, title_kr, genre, genre_kr, url, is_riverse)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                date,
                platform,
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


def save_works_metadata(platform: str, works: List[Dict[str, Any]]):
    """
    작품 메타데이터 저장/갱신 (thumbnail_url 등 캐싱)

    Args:
        platform: 플랫폼 이름
        works: [{'title': str, 'thumbnail_url': str, 'url': str}, ...]
    """
    if not works:
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    count = 0
    for item in works:
        title = item.get('title', '')
        thumbnail_url = item.get('thumbnail_url', '')
        url = item.get('url', '')

        if not title or not thumbnail_url:
            continue

        cursor.execute('''
            INSERT INTO works (platform, title, thumbnail_url, url, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(platform, title)
            DO UPDATE SET
                thumbnail_url = excluded.thumbnail_url,
                url = excluded.url,
                updated_at = CURRENT_TIMESTAMP
        ''', (platform, title, thumbnail_url, url))
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT title, thumbnail_url
        FROM works
        WHERE platform = ? AND thumbnail_url IS NOT NULL AND thumbnail_url != ''
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE works SET thumbnail_base64 = ?, updated_at = CURRENT_TIMESTAMP
        WHERE platform = ? AND title = ?
    ''', (b64_data, platform, title))
    conn.commit()
    conn.close()


def get_thumbnails_base64(platform: str) -> Dict[str, str]:
    """
    플랫폼의 모든 작품 썸네일 base64 맵 반환

    Returns:
        {title: "data:image/...;base64,..."} 딕셔너리
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, thumbnail_base64
        FROM works
        WHERE platform = ? AND thumbnail_base64 IS NOT NULL AND thumbnail_base64 != ''
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, thumbnail_url
        FROM works
        WHERE platform = ?
          AND thumbnail_url IS NOT NULL AND thumbnail_url != ''
          AND (thumbnail_base64 IS NULL OR thumbnail_base64 = '')
    ''', (platform,))
    result = [{'title': row[0], 'thumbnail_url': row[1]} for row in cursor.fetchall()]
    conn.close()
    return result


def backup_to_json(date: str, platform: str, rankings: List[Dict[str, Any]]):
    """
    JSON 백업 저장 (SQLite 장애 대비)

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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT date, rank
        FROM rankings
        WHERE title = ? AND platform = ?
        ORDER BY date DESC
        LIMIT ?
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT DISTINCT date
        FROM rankings
        WHERE date < ? AND platform = ?
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

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 현재 날짜 랭킹
    cursor.execute('''
        SELECT title, rank
        FROM rankings
        WHERE date = ? AND platform = ?
    ''', (date, platform))
    current = {row[0]: row[1] for row in cursor.fetchall()}

    # 이전 날짜 랭킹
    cursor.execute('''
        SELECT title, rank
        FROM rankings
        WHERE date = ? AND platform = ?
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
    # 테스트 실행
    init_db()
    print("\n✅ DB 초기화 테스트 완료")

    # 샘플 데이터 삽입
    test_data = [
        {
            'rank': 1,
            'title': 'テスト作品1',
            'genre': 'ファンタジー',
            'url': 'https://test.com/1'
        },
        {
            'rank': 2,
            'title': '俺だけレベルアップな件',
            'genre': 'アクション',
            'url': 'https://test.com/2'
        }
    ]

    today = datetime.now().strftime('%Y-%m-%d')
    save_rankings(today, 'test', test_data)
    backup_to_json(today, 'test', test_data)

    print("\n✅ 샘플 데이터 저장 테스트 완료")
