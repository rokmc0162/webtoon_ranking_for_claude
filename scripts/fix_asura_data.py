#!/usr/bin/env python3
"""
Asura 데이터 수정 스크립트:
1. 중복 제목 병합 (truncated vs full)
2. 미매핑 Asura 영문 제목 → title_kr 생성 (fallback: 영문 그대로)
3. unified_work_id 백필
4. title_en 백필
"""
import json
import os
import re
import sys

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.db import get_db_connection, _upsert_unified_work
from crawler.utils import get_korean_title, is_riverse_title


def normalize_title(title: str) -> str:
    """제목 정규화 (비교용)"""
    return re.sub(r'[^a-z0-9]', '', title.lower())


def step1_merge_duplicates():
    """Step 1: Asura 중복 제목 병합"""
    print("\n" + "=" * 60)
    print("Step 1: Asura 중복 제목 병합")
    print("=" * 60)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, title, url, author, description, rating FROM works WHERE platform = 'asura'")
    works = cur.fetchall()

    # 정규화 기준으로 그룹핑
    groups = {}
    for wid, title, url, author, desc, rating in works:
        norm = normalize_title(title)
        if norm not in groups:
            groups[norm] = []
        groups[norm].append({
            'id': wid, 'title': title, 'url': url,
            'author': author or '', 'desc': desc or '', 'rating': rating
        })

    merged = 0
    for norm, group in groups.items():
        if len(group) <= 1:
            continue

        # 가장 좋은 항목 선택: 긴 제목 + 데이터가 많은 것
        group.sort(key=lambda x: (
            len(x['author']) + len(x['desc']),  # 데이터 풍부함
            len(x['title']),                      # 긴 제목
            -x['id']                               # 최신 ID
        ), reverse=True)
        keep = group[0]
        removes = group[1:]

        for rm in removes:
            print(f"  병합: \"{rm['title'][:50]}\" → \"{keep['title'][:50]}\"")

            # 1. reviews 이동
            cur.execute("""
                UPDATE reviews SET work_title = %s
                WHERE platform = 'asura' AND work_title = %s
                AND NOT EXISTS (
                    SELECT 1 FROM reviews r2
                    WHERE r2.platform = 'asura' AND r2.work_title = %s
                      AND r2.reviewer_name = reviews.reviewer_name
                      AND r2.reviewed_at = reviews.reviewed_at
                )
            """, (keep['title'], rm['title'], keep['title']))

            # 2. rankings 이동
            cur.execute("""
                UPDATE rankings SET title = %s
                WHERE platform = 'asura' AND title = %s
                AND NOT EXISTS (
                    SELECT 1 FROM rankings r2
                    WHERE r2.platform = 'asura' AND r2.title = %s
                      AND r2.date = rankings.date
                      AND r2.sub_category = rankings.sub_category
                      AND r2.rank = rankings.rank
                )
            """, (keep['title'], rm['title'], keep['title']))

            # 3. 남은 orphan 삭제
            cur.execute("DELETE FROM reviews WHERE platform = 'asura' AND work_title = %s", (rm['title'],))
            cur.execute("DELETE FROM rankings WHERE platform = 'asura' AND title = %s", (rm['title'],))

            # 4. works 행 삭제
            cur.execute("DELETE FROM works WHERE id = %s", (rm['id'],))
            merged += 1

    conn.commit()
    conn.close()
    print(f"✅ 중복 병합 완료: {merged}개 제거")


def step2_generate_mappings():
    """Step 2: 미매핑 Asura 작품에 대해 title_kr 매핑 생성"""
    print("\n" + "=" * 60)
    print("Step 2: Asura 영문 제목 매핑 생성")
    print("=" * 60)

    conn = get_db_connection()
    cur = conn.cursor()

    # 매핑 없는 Asura works
    cur.execute("""
        SELECT title FROM works
        WHERE platform = 'asura' AND (title_kr IS NULL OR title_kr = '')
        ORDER BY title
    """)
    unlinked = [r[0] for r in cur.fetchall()]
    print(f"매핑 필요: {len(unlinked)}개")

    if not unlinked:
        conn.close()
        return

    # unified_works에서 크로스 레퍼런스 검색
    cur.execute("SELECT id, title_kr, title_canonical, title_en FROM unified_works")
    unified = cur.fetchall()

    # title_mappings.json 로드
    mappings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  'data', 'title_mappings.json')
    with open(mappings_path, 'r', encoding='utf-8') as f:
        mappings = json.load(f)

    new_mappings = {}
    fallback_count = 0
    cross_ref_count = 0

    for en_title in unlinked:
        en_norm = normalize_title(en_title)

        # 방법 1: unified_works.title_canonical 또는 title_en과 매칭
        found = False
        for uid, tkr, tcanon, ten in unified:
            if tcanon and normalize_title(tcanon) == en_norm:
                new_mappings[en_title] = tkr
                cross_ref_count += 1
                found = True
                break
            if ten and normalize_title(ten) == en_norm:
                new_mappings[en_title] = tkr
                cross_ref_count += 1
                found = True
                break

        if found:
            continue

        # 방법 2: 기존 매핑의 값에서 역방향 검색 (EN value → KR)
        for key, kr in mappings.items():
            if normalize_title(key) == en_norm:
                new_mappings[en_title] = kr
                cross_ref_count += 1
                found = True
                break

        if found:
            continue

        # 방법 3: 영문 제목 그대로 title_kr로 사용 (fallback)
        new_mappings[en_title] = en_title
        fallback_count += 1

    # title_mappings.json 업데이트
    mappings.update(new_mappings)
    with open(mappings_path, 'w', encoding='utf-8') as f:
        json.dump(mappings, f, ensure_ascii=False, indent=2, sort_keys=True)

    conn.close()
    print(f"✅ 매핑 생성 완료: {len(new_mappings)}개")
    print(f"   크로스 레퍼런스: {cross_ref_count}개")
    print(f"   영문 fallback: {fallback_count}개")


def step3_backfill_links():
    """Step 3: 모든 Asura works에 unified_work_id + title_kr 백필"""
    print("\n" + "=" * 60)
    print("Step 3: Asura unified_work_id 백필")
    print("=" * 60)

    # utils 모듈의 캐시 초기화 (새 매핑 반영)
    from crawler import utils
    utils._title_mappings = None

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, title_kr, unified_work_id
        FROM works WHERE platform = 'asura'
        ORDER BY title
    """)
    works = cur.fetchall()

    linked = 0
    updated = 0
    for wid, title, existing_kr, existing_uwid in works:
        title_kr = get_korean_title(title)

        if not title_kr:
            # 매핑에도 없으면 영문 그대로 사용
            title_kr = title

        is_riv = is_riverse_title(title)

        # unified_work upsert
        uwid = _upsert_unified_work(
            cur, title_kr, title,
            is_riverse=is_riv,
            title_en=title,
        )

        if uwid:
            # works 행 업데이트
            cur.execute("""
                UPDATE works SET
                    unified_work_id = %s,
                    title_kr = %s,
                    is_riverse = is_riverse OR %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (uwid, title_kr, is_riv, wid))

            if not existing_uwid:
                linked += 1
            else:
                updated += 1

    conn.commit()
    conn.close()
    print(f"✅ 백필 완료: 신규 링크 {linked}개, 업데이트 {updated}개")


def step4_backfill_title_en():
    """Step 4: 기존 unified_works에 Asura 영문 제목 백필"""
    print("\n" + "=" * 60)
    print("Step 4: title_en 백필")
    print("=" * 60)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE unified_works uw
        SET title_en = w.title, updated_at = NOW()
        FROM works w
        WHERE w.unified_work_id = uw.id
          AND w.platform = 'asura'
          AND (uw.title_en IS NULL OR uw.title_en = '')
    """)
    count = cur.rowcount
    conn.commit()
    conn.close()
    print(f"✅ title_en 백필 완료: {count}개 업데이트")


def verify():
    """검증"""
    print("\n" + "=" * 60)
    print("검증")
    print("=" * 60)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*), COUNT(unified_work_id),
               COUNT(CASE WHEN title_kr <> '' AND title_kr IS NOT NULL THEN 1 END)
        FROM works WHERE platform = 'asura'
    """)
    r = cur.fetchone()
    print(f"Asura works: {r[0]}개 total, linked={r[1]}, title_kr={r[2]}")

    cur.execute("SELECT COUNT(*) FROM unified_works WHERE title_en <> '' AND title_en IS NOT NULL")
    print(f"unified_works with title_en: {cur.fetchone()[0]}개")

    # 나노마신 체크
    cur.execute("""
        SELECT w.platform, w.title, w.unified_work_id, uw.title_kr, uw.title_en
        FROM works w
        LEFT JOIN unified_works uw ON w.unified_work_id = uw.id
        WHERE (w.title ILIKE '%nano machine%' OR uw.title_kr LIKE '%나노마신%')
        ORDER BY w.platform
    """)
    print(f"\n나노마신 크로스 플랫폼:")
    for r in cur.fetchall():
        print(f"  {r[0]:12} {r[1][:30]:30} uwid={r[2]} kr={r[3][:15] if r[3] else ''} en={r[4][:20] if r[4] else ''}")

    conn.close()


if __name__ == '__main__':
    print("🔧 Asura 데이터 수정 시작")
    step1_merge_duplicates()
    step2_generate_mappings()
    step3_backfill_links()
    step4_backfill_title_en()
    verify()
    print("\n✅ 모든 수정 완료!")
