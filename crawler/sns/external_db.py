"""
외부 데이터 DB 저장/조회 (external_ids + external_data 테이블)
"""
import psycopg2
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / '.env')
load_dotenv(project_root / 'dashboard-next' / '.env.local')
DATABASE_URL = os.environ.get('SUPABASE_DB_URL', '')


def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


def get_cached_external_id(title: str, source: str) -> Optional[str]:
    """캐시된 외부 ID 조회. 없으면 None."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'SELECT external_id FROM external_ids WHERE title = %s AND source = %s LIMIT 1',
        (title, source)
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def save_external_id(platform: str, title: str, source: str,
                     external_id: str, external_title: str = '',
                     match_score: float = 1.0):
    """외부 ID 매핑 저장 (UPSERT)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO external_ids
        (platform, title, source, external_id, external_title, match_score, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (platform, title, source)
        DO UPDATE SET
            external_id = EXCLUDED.external_id,
            external_title = EXCLUDED.external_title,
            match_score = EXCLUDED.match_score,
            updated_at = NOW()
    ''', (platform, title, source, external_id, external_title, match_score))
    conn.commit()
    conn.close()


def save_external_metrics_batch(title: str, source: str,
                                metrics: Dict[str, Any],
                                collected_date: str = ''):
    """메트릭 여러 개를 한 트랜잭션으로 저장."""
    date = collected_date or datetime.now().strftime('%Y-%m-%d')
    conn = get_db_connection()
    cur = conn.cursor()
    for metric_name, value in metrics.items():
        if isinstance(value, str):
            cur.execute('''
                INSERT INTO external_data
                (title, source, metric_name, metric_value, metric_text, collected_date)
                VALUES (%s, %s, %s, NULL, %s, %s::date)
                ON CONFLICT (title, source, metric_name, collected_date)
                DO UPDATE SET metric_text = EXCLUDED.metric_text, collected_at = NOW()
            ''', (title, source, metric_name, value, date))
        elif value is not None:
            cur.execute('''
                INSERT INTO external_data
                (title, source, metric_name, metric_value, collected_date)
                VALUES (%s, %s, %s, %s, %s::date)
                ON CONFLICT (title, source, metric_name, collected_date)
                DO UPDATE SET metric_value = EXCLUDED.metric_value, collected_at = NOW()
            ''', (title, source, metric_name, float(value), date))
    conn.commit()
    conn.close()


def get_external_data(title: str) -> List[Dict[str, Any]]:
    """타이틀의 최신 외부 데이터 조회 (소스+메트릭별 최신 1건)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT DISTINCT ON (source, metric_name)
            source, metric_name, metric_value, metric_text, collected_date
        FROM external_data
        WHERE title = %s
        ORDER BY source, metric_name, collected_date DESC
    ''', (title,))
    result = [{
        'source': r[0], 'metric_name': r[1],
        'metric_value': r[2], 'metric_text': r[3],
        'collected_date': str(r[4])
    } for r in cur.fetchall()]
    conn.close()
    return result


def get_works_for_external(max_count: int = 200, riverse_only: bool = False,
                           asura_only: bool = False) -> List[Dict[str, str]]:
    """외부 데이터 수집 대상 작품 목록.

    Args:
        max_count: 최대 작품 수
        riverse_only: True이면 리버스 작품만 (날짜 제한 해제)
        asura_only: True이면 Asura 작품만 (날짜 제한 해제)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    if riverse_only:
        cur.execute('''
            SELECT DISTINCT w.title, w.platform
            FROM works w
            WHERE w.is_riverse = TRUE
            ORDER BY w.title
            LIMIT %s
        ''', (max_count,))
    elif asura_only:
        cur.execute('''
            SELECT DISTINCT w.title, w.platform
            FROM works w
            WHERE w.platform = 'asura'
            ORDER BY w.title
            LIMIT %s
        ''', (max_count,))
    else:
        cur.execute('''
            SELECT DISTINCT w.title, w.platform
            FROM works w
            WHERE w.last_seen_date >= (CURRENT_DATE - INTERVAL '14 days')::date
            ORDER BY w.title
            LIMIT %s
        ''', (max_count,))
    result = [{'title': r[0], 'platform': r[1]} for r in cur.fetchall()]
    conn.close()
    return result
