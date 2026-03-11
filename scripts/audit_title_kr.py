#!/usr/bin/env python3
"""
한국어 제목(title_kr) 전수검사 및 클리닝 스크립트

1. title_mappings.json 품질 감사 (쓰레기/음역/비제목 탐지)
2. 문제 항목 클리닝 + Claude API 재번역
3. DB (works + rankings) 업데이트
4. unified_works 재연결

사용법:
    python3 scripts/audit_title_kr.py --audit     # 현황 보고만
    python3 scripts/audit_title_kr.py --fix        # 감사 + 클리닝 + DB 업데이트
"""

import os
import sys
import json
import re
import time
import argparse
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / '.env')
load_dotenv(project_root / 'dashboard-next' / '.env.local', override=True)

import psycopg2

DB_URL = os.environ.get('SUPABASE_DB_URL', '')
API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
MAPPINGS_PATH = project_root / 'data' / 'title_mappings.json'
BATCH_SIZE = 80


# ─── 탐지 함수 ───────────────────────────────────────────────

JP_PATTERN = re.compile(r'[\u3041-\u3096\u30A1-\u30F6\u4E00-\u9FFF]')
KR_PARTICLE_PATTERN = re.compile(r'을/를|이/가|은/는|와/과')
PHONETIC_PATTERNS = re.compile(
    r'타치|라레|테모|세루|테오다|키타|나테이타|코은푸레쿠스|'
    r'시테|사레|마시타|데스|쿠다사이|오네가이|'
    r'하여합니다|하여키타|하여오다|라레타'
)
JUNK_KEY_PATTERN = re.compile(r'^\d+位$')
NUMBER_KEY_PATTERN = re.compile(r'^[\d.]+万$')
PROMO_KEYWORDS = ['巻分無料', '割引セール', '割引', '無料増', 'ポイント還元']


def has_japanese(s: str) -> bool:
    return bool(JP_PATTERN.search(s))


def has_korean_particle(s: str) -> bool:
    return bool(KR_PARTICLE_PATTERN.search(s))


def has_phonetic_pattern(s: str) -> bool:
    return bool(PHONETIC_PATTERNS.search(s))


def detect_bad_entries(mappings: dict) -> dict:
    """분류: junk(비제목), garbage(혼합문자), phonetic(음역)"""
    bad = {"junk": [], "garbage": [], "phonetic": []}

    for jp, kr in mappings.items():
        # 1) 비제목 키: 순위, 숫자, 프로모션
        if JUNK_KEY_PATTERN.match(jp) or NUMBER_KEY_PATTERN.match(jp):
            bad["junk"].append(jp)
            continue
        if any(kw in jp for kw in PROMO_KEYWORDS):
            bad["junk"].append(jp)
            continue

        # 값이 비어있으면 스킵
        if not kr or not kr.strip():
            continue

        # 2) 혼합 쓰레기: value에 일본 문자 + 한국 조사 혼재
        if has_japanese(kr) and has_korean_particle(kr):
            bad["garbage"].append(jp)
            continue

        # 3) 음역 패턴: value에 일본어→한국어 음역
        if has_phonetic_pattern(kr) and has_japanese(jp):
            bad["phonetic"].append(jp)
            continue

    return bad


# ─── JSON 파싱 ───────────────────────────────────────────────

def extract_json(text: str) -> dict:
    """응답 텍스트에서 JSON 객체 추출"""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0].strip()
    start = text.find("{")
    if start == -1:
        return {}
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    break
    return {}


# ─── Claude API 번역 ─────────────────────────────────────────

def translate_batch(client, titles: list[str], retry: int = 0) -> dict[str, str]:
    """Claude API로 일본어 제목을 한국어로 번역"""
    titles_text = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        messages=[{
            "role": "user",
            "content": f"""다음 일본어 만화/웹툰 제목들을 한국어로 번역해주세요.

규칙:
- 한국 웹툰이 일본어로 번역된 것이면 원래 한국어 제목을 찾아서 적어주세요
- 일본 원작이면 자연스러운 한국어로 번역해주세요
- 영어 제목은 그대로 유지해도 됩니다
- 고유명사(캐릭터명 등)는 음역하세요
- 【】 같은 특수 괄호 안의 내용(판본 정보)은 그대로 유지하세요
- 반드시 JSON 형식으로만 응답하세요: {{"원본제목": "한국어제목", ...}}
- 다른 텍스트 없이 JSON만 출력하세요

제목 목록:
{titles_text}"""
        }]
    )

    text = response.content[0].text.strip()
    result = extract_json(text)

    if not result and retry < 2:
        print(f"  ⚠️ JSON 파싱 실패, 재시도 ({retry + 1}/2)...")
        time.sleep(2)
        return translate_batch(client, titles, retry + 1)

    return result


# ─── DB 함수 ─────────────────────────────────────────────────

def get_db_missing_titles() -> list[str]:
    """DB에서 title_kr 누락된 고유 제목 수집"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT title FROM works
        WHERE (title_kr IS NULL OR title_kr = '')
        ORDER BY title
    """)
    titles = [row[0] for row in cur.fetchall()]
    conn.close()
    return titles


def get_db_stats() -> dict:
    """DB 현황 통계"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    stats = {}

    # works 테이블
    cur.execute("SELECT COUNT(*) FROM works")
    stats["works_total"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM works WHERE title_kr IS NULL OR title_kr = ''")
    stats["works_empty_kr"] = cur.fetchone()[0]

    # rankings 테이블
    cur.execute("SELECT COUNT(DISTINCT title) FROM rankings WHERE title_kr IS NULL OR title_kr = ''")
    stats["rankings_empty_kr_titles"] = cur.fetchone()[0]

    # unified_works 테이블
    cur.execute("SELECT COUNT(*) FROM unified_works")
    stats["unified_total"] = cur.fetchone()[0]

    # works without unified link
    cur.execute("SELECT COUNT(*) FROM works WHERE unified_work_id IS NULL")
    stats["works_no_unified"] = cur.fetchone()[0]

    # works with bad title_kr (containing Japanese chars)
    cur.execute("""
        SELECT COUNT(*) FROM works
        WHERE title_kr ~ '[ぁ-んァ-ヶ一-龥]'
        AND title_kr ~ '[ㄱ-ㅣ가-힣]'
    """)
    stats["works_mixed_kr"] = cur.fetchone()[0]

    conn.close()
    return stats


def update_db_title_kr(translations: dict[str, str]):
    """DB의 works와 rankings 테이블에 title_kr 업데이트"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    w_total = r_total = 0

    for jp_title, kr_title in translations.items():
        if not kr_title:
            continue
        cur.execute("""
            UPDATE works SET title_kr = %s
            WHERE title = %s AND (title_kr IS NULL OR title_kr = '' OR
                  (title_kr ~ '[ぁ-んァ-ヶ一-龥]' AND title_kr ~ '[ㄱ-ㅣ가-힣]'))
        """, (kr_title, jp_title))
        w_total += cur.rowcount

        cur.execute("""
            UPDATE rankings SET title_kr = %s
            WHERE title = %s AND (title_kr IS NULL OR title_kr = '' OR
                  (title_kr ~ '[ぁ-んァ-ヶ一-龥]' AND title_kr ~ '[ㄱ-ㅣ가-힣]'))
        """, (kr_title, jp_title))
        r_total += cur.rowcount

    conn.commit()
    conn.close()
    return w_total, r_total


def relink_unified_works():
    """title_kr이 있지만 unified_work_id가 없는 works를 unified_works에 연결"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # title_kr이 있는데 unified_work_id가 NULL인 works 가져오기
    cur.execute("""
        SELECT DISTINCT ON (title_kr) title_kr, title, genre, genre_kr,
               is_riverse, thumbnail_url, thumbnail_base64, author, publisher
        FROM works
        WHERE title_kr IS NOT NULL AND title_kr != ''
          AND unified_work_id IS NULL
        ORDER BY title_kr, last_seen_date DESC NULLS LAST
    """)
    orphans = cur.fetchall()

    if not orphans:
        print("  ✅ 고아 작품 없음")
        conn.close()
        return 0

    linked = 0
    for row in orphans:
        title_kr, title, genre, genre_kr, is_riverse, thumb_url, thumb_b64, author, publisher = row

        # unified_works에 upsert
        cur.execute('''
            INSERT INTO unified_works
                (title_kr, title_canonical, author, publisher, genre, genre_kr,
                 is_riverse, thumbnail_url, thumbnail_base64)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (title_kr) DO UPDATE SET
                title_canonical = COALESCE(NULLIF(EXCLUDED.title_canonical, ''), unified_works.title_canonical),
                author = COALESCE(NULLIF(EXCLUDED.author, ''), unified_works.author),
                is_riverse = EXCLUDED.is_riverse OR unified_works.is_riverse,
                thumbnail_url = COALESCE(NULLIF(EXCLUDED.thumbnail_url, ''), unified_works.thumbnail_url),
                updated_at = NOW()
            RETURNING id
        ''', (title_kr, title, author or '', publisher or '', genre or '',
              genre_kr or '', is_riverse or False, thumb_url or '', thumb_b64 or ''))
        uid_row = cur.fetchone()
        if uid_row:
            uid = uid_row[0]
            cur.execute("""
                UPDATE works SET unified_work_id = %s
                WHERE title_kr = %s AND unified_work_id IS NULL
            """, (uid, title_kr))
            linked += cur.rowcount

    conn.commit()
    conn.close()
    return linked


# ─── 매핑 저장 ────────────────────────────────────────────────

def save_mappings(mappings: dict):
    """title_mappings.json 정렬 후 저장"""
    sorted_m = dict(sorted(mappings.items()))
    with open(MAPPINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(sorted_m, f, ensure_ascii=False, indent=2)
    return len(sorted_m)


# ─── 메인 ─────────────────────────────────────────────────────

def run_audit(mappings: dict):
    """현황 감사 보고"""
    print("\n" + "=" * 60)
    print("📋 title_mappings.json 감사")
    print("=" * 60)
    print(f"  총 매핑: {len(mappings)}개")

    bad = detect_bad_entries(mappings)

    print(f"\n  🗑️  비제목(junk): {len(bad['junk'])}개")
    if bad['junk']:
        for k in bad['junk'][:10]:
            print(f"     {k} → {mappings[k]}")
        if len(bad['junk']) > 10:
            print(f"     ... 외 {len(bad['junk']) - 10}개")

    print(f"\n  💀 혼합 쓰레기(garbage): {len(bad['garbage'])}개")
    if bad['garbage']:
        for k in bad['garbage'][:10]:
            print(f"     {k}")
            print(f"       → {mappings[k][:60]}...")
        if len(bad['garbage']) > 10:
            print(f"     ... 외 {len(bad['garbage']) - 10}개")

    print(f"\n  🔤 음역(phonetic): {len(bad['phonetic'])}개")
    if bad['phonetic']:
        for k in bad['phonetic'][:10]:
            print(f"     {k} → {mappings[k]}")
        if len(bad['phonetic']) > 10:
            print(f"     ... 외 {len(bad['phonetic']) - 10}개")

    total_bad = len(bad['junk']) + len(bad['garbage']) + len(bad['phonetic'])
    print(f"\n  📊 총 문제: {total_bad}개 / {len(mappings)}개 ({total_bad*100/len(mappings):.1f}%)")

    # DB 현황
    print("\n" + "=" * 60)
    print("📋 DB 현황")
    print("=" * 60)

    stats = get_db_stats()
    print(f"  works 총: {stats['works_total']}개")
    print(f"  works title_kr 비어있음: {stats['works_empty_kr']}개")
    print(f"  works 혼합 title_kr: {stats['works_mixed_kr']}개")
    print(f"  rankings title_kr 비어있는 고유제목: {stats['rankings_empty_kr_titles']}개")
    print(f"  unified_works 총: {stats['unified_total']}개")
    print(f"  works → unified 미연결: {stats['works_no_unified']}개")

    # DB 누락 제목
    missing = get_db_missing_titles()
    print(f"\n  DB에서 title_kr 누락된 고유제목: {len(missing)}개")
    if missing:
        for t in missing[:15]:
            print(f"     {t}")
        if len(missing) > 15:
            print(f"     ... 외 {len(missing) - 15}개")

    return bad, stats, missing


def run_fix(mappings: dict, bad: dict, missing_titles: list[str]):
    """클리닝 + 재번역 + DB 업데이트"""
    import anthropic

    if not API_KEY:
        print("❌ ANTHROPIC_API_KEY 없음 — 재번역 불가")
        return

    client = anthropic.Anthropic(api_key=API_KEY)

    # ── Phase 1: junk 삭제 ──
    print(f"\n{'='*60}")
    print("🗑️  Phase 1: 비제목 항목 삭제")
    print(f"{'='*60}")
    for k in bad['junk']:
        del mappings[k]
    print(f"  ✅ {len(bad['junk'])}개 삭제")

    # ── Phase 2: garbage + phonetic 재번역 ──
    retranslate_keys = bad['garbage'] + bad['phonetic']
    print(f"\n{'='*60}")
    print(f"🔄 Phase 2: {len(retranslate_keys)}개 재번역")
    print(f"{'='*60}")

    if retranslate_keys:
        total_translated = 0
        for i in range(0, len(retranslate_keys), BATCH_SIZE):
            batch = retranslate_keys[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(retranslate_keys) + BATCH_SIZE - 1) // BATCH_SIZE
            print(f"\n  📝 배치 {batch_num}/{total_batches} ({len(batch)}개)...")

            try:
                translations = translate_batch(client, batch)
            except Exception as e:
                print(f"  ❌ API 오류: {e}")
                break

            if translations:
                for jp, kr in translations.items():
                    if kr:
                        mappings[jp] = kr
                total_translated += len(translations)
                print(f"  ✅ {len(translations)}개 재번역 완료")
            else:
                print(f"  ⚠️ 결과 없음")

            if i + BATCH_SIZE < len(retranslate_keys):
                time.sleep(1)

        print(f"\n  📊 총 {total_translated}개 재번역 완료")

    # ── Phase 3: 매핑 저장 ──
    total = save_mappings(mappings)
    print(f"\n  💾 title_mappings.json 저장 (총 {total}개)")

    # ── Phase 4: DB 업데이트 (재번역된 항목) ──
    print(f"\n{'='*60}")
    print("💾 Phase 3: DB 업데이트 (재번역 반영)")
    print(f"{'='*60}")

    retranslated = {k: mappings[k] for k in retranslate_keys if k in mappings}
    if retranslated:
        w, r = update_db_title_kr(retranslated)
        print(f"  works: {w}행, rankings: {r}행 업데이트")

    # ── Phase 5: DB 누락 채우기 ──
    print(f"\n{'='*60}")
    print("🔤 Phase 4: DB 누락 title_kr 채우기")
    print(f"{'='*60}")

    # 5-1. 매핑으로 먼저 복구
    already_mapped = {}
    still_missing = []
    for t in missing_titles:
        if t in mappings:
            already_mapped[t] = mappings[t]
        else:
            # case-insensitive
            found = False
            for k, v in mappings.items():
                if k.lower() == t.lower():
                    already_mapped[t] = v
                    found = True
                    break
            if not found:
                still_missing.append(t)

    if already_mapped:
        print(f"  🔄 기존 매핑 복구: {len(already_mapped)}개")
        w, r = update_db_title_kr(already_mapped)
        print(f"     works: {w}행, rankings: {r}행")

    # 5-2. 남은 것 API 번역
    if still_missing:
        print(f"  🤖 번역 필요: {len(still_missing)}개")
        total_new = 0
        for i in range(0, len(still_missing), BATCH_SIZE):
            batch = still_missing[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(still_missing) + BATCH_SIZE - 1) // BATCH_SIZE
            print(f"\n  📝 배치 {batch_num}/{total_batches} ({len(batch)}개)...")

            try:
                translations = translate_batch(client, batch)
            except Exception as e:
                if 'credit' in str(e).lower():
                    print(f"  ❌ API 크레딧 부족 — 중단")
                    break
                print(f"  ❌ API 오류: {e}")
                break

            if translations:
                # DB 업데이트
                w, r = update_db_title_kr(translations)
                # 매핑 추가
                added = 0
                for jp, kr in translations.items():
                    if kr and jp not in mappings:
                        mappings[jp] = kr
                        added += 1
                save_mappings(mappings)
                total_new += len(translations)
                print(f"  ✅ {len(translations)}개 / DB: w{w} r{r} / 매핑: +{added}")

            if i + BATCH_SIZE < len(still_missing):
                time.sleep(1)

        print(f"\n  📊 총 {total_new}개 신규 번역")
    else:
        print("  ✅ 누락 없음!")

    # ── Phase 6: unified_works 재연결 ──
    print(f"\n{'='*60}")
    print("🔗 Phase 5: unified_works 재연결")
    print(f"{'='*60}")

    linked = relink_unified_works()
    print(f"  ✅ {linked}개 작품 연결")

    # ── 최종 보고 ──
    print(f"\n{'='*60}")
    print("✅ 완료!")
    print(f"{'='*60}")
    final_stats = get_db_stats()
    print(f"  works title_kr 비어있음: {final_stats['works_empty_kr']}개")
    print(f"  works 혼합 title_kr: {final_stats['works_mixed_kr']}개")
    print(f"  works → unified 미연결: {final_stats['works_no_unified']}개")
    print(f"  unified_works 총: {final_stats['unified_total']}개")


def main():
    parser = argparse.ArgumentParser(description='한국어 제목 전수검사 및 클리닝')
    parser.add_argument('--audit', action='store_true', help='현황 보고만')
    parser.add_argument('--fix', action='store_true', help='클리닝 + 재번역 + DB 업데이트')
    args = parser.parse_args()

    if not args.audit and not args.fix:
        print("사용법:")
        print("  python3 scripts/audit_title_kr.py --audit   # 현황 보고")
        print("  python3 scripts/audit_title_kr.py --fix     # 클리닝 + 수정")
        return

    # 매핑 로드
    with open(MAPPINGS_PATH, 'r', encoding='utf-8') as f:
        mappings = json.load(f)

    # 감사
    bad, stats, missing = run_audit(mappings)

    # 수정
    if args.fix:
        run_fix(mappings, bad, missing)


if __name__ == "__main__":
    main()
