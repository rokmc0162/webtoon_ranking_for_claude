#!/usr/bin/env python3
"""
title_kr 누락 작품 일괄 번역 스크립트

1. DB에서 title_kr이 비어있는 고유 일본어 제목 수집
2. Claude API로 배치 번역 (50개씩)
3. title_mappings.json 업데이트
4. DB (works + rankings) 업데이트
"""

import os
import sys
import json
import time
import anthropic
import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'dashboard-next', '.env.local'), override=True)

DB_URL = os.environ['SUPABASE_DB_URL']
API_KEY = os.environ['ANTHROPIC_API_KEY']
MAPPINGS_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'title_mappings.json')

BATCH_SIZE = 80  # Claude에 한 번에 보내는 제목 수


def get_missing_titles() -> list[str]:
    """DB에서 title_kr이 비어있는 고유 제목 수집"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # works 테이블에서 title_kr 누락된 고유 title
    cur.execute("""
        SELECT DISTINCT title FROM works
        WHERE (title_kr IS NULL OR title_kr = '')
        ORDER BY title
    """)
    titles = [row[0] for row in cur.fetchall()]
    conn.close()
    return titles


def extract_json(text: str) -> dict:
    """응답 텍스트에서 JSON 객체 추출 (robust)"""
    import re
    # ```json ... ``` 래핑 제거
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0].strip()

    # 가장 바깥 { } 찾기
    start = text.find("{")
    if start == -1:
        return {}

    # 중첩 { } 카운팅으로 매칭되는 } 찾기
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


def translate_batch(client: anthropic.Anthropic, titles: list[str], retry: int = 0) -> dict[str, str]:
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


def update_db(translations: dict[str, str]):
    """DB의 works와 rankings 테이블에 title_kr 업데이트"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    works_updated = 0
    rankings_updated = 0

    for jp_title, kr_title in translations.items():
        if not kr_title:
            continue

        # works 업데이트
        cur.execute("""
            UPDATE works SET title_kr = %s
            WHERE title = %s AND (title_kr IS NULL OR title_kr = '')
        """, (kr_title, jp_title))
        works_updated += cur.rowcount

        # rankings 업데이트
        cur.execute("""
            UPDATE rankings SET title_kr = %s
            WHERE title = %s AND (title_kr IS NULL OR title_kr = '')
        """, (kr_title, jp_title))
        rankings_updated += cur.rowcount

    conn.commit()
    conn.close()
    return works_updated, rankings_updated


def update_mappings(translations: dict[str, str]):
    """title_mappings.json에 새 매핑 추가"""
    with open(MAPPINGS_PATH, 'r', encoding='utf-8') as f:
        mappings = json.load(f)

    added = 0
    for jp_title, kr_title in translations.items():
        if kr_title and jp_title not in mappings:
            mappings[jp_title] = kr_title
            added += 1

    # 키 기준 정렬 후 저장
    sorted_mappings = dict(sorted(mappings.items()))
    with open(MAPPINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(sorted_mappings, f, ensure_ascii=False, indent=2)

    return added, len(sorted_mappings)


def main():
    print("=" * 60)
    print("title_kr 누락 작품 일괄 번역")
    print("=" * 60)

    # 1. 누락 제목 수집
    missing = get_missing_titles()
    print(f"\n📊 title_kr 누락 고유 제목: {len(missing)}개")

    if not missing:
        print("✅ 누락 없음!")
        return

    # 기존 매핑에서 이미 있는 것 먼저 적용
    with open(MAPPINGS_PATH, 'r', encoding='utf-8') as f:
        existing_mappings = json.load(f)

    already_mapped = {}
    still_missing = []
    for t in missing:
        if t in existing_mappings:
            already_mapped[t] = existing_mappings[t]
        else:
            # 대소문자 무시 체크
            found = False
            for k, v in existing_mappings.items():
                if k.lower() == t.lower():
                    already_mapped[t] = v
                    found = True
                    break
            if not found:
                still_missing.append(t)

    if already_mapped:
        print(f"\n🔄 기존 매핑으로 {len(already_mapped)}개 복구 중...")
        w, r = update_db(already_mapped)
        print(f"   works: {w}행, rankings: {r}행 업데이트")

    print(f"\n🤖 번역 필요: {len(still_missing)}개")

    if not still_missing:
        print("✅ 모든 제목 복구 완료!")
        return

    # 2. 배치 번역
    client = anthropic.Anthropic(api_key=API_KEY)
    all_translations = {}

    for i in range(0, len(still_missing), BATCH_SIZE):
        batch = still_missing[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(still_missing) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\n📝 배치 {batch_num}/{total_batches} ({len(batch)}개 번역 중)...")

        translations = translate_batch(client, batch)
        all_translations.update(translations)
        print(f"   ✅ {len(translations)}개 번역 완료")

        if i + BATCH_SIZE < len(still_missing):
            time.sleep(1)  # rate limit 대비

    # 3. DB 업데이트
    print(f"\n💾 DB 업데이트 중...")
    w, r = update_db(all_translations)
    print(f"   works: {w}행, rankings: {r}행 업데이트")

    # 4. title_mappings.json 업데이트
    added, total = update_mappings(all_translations)
    print(f"\n📁 title_mappings.json: {added}개 추가 (총 {total}개)")

    # 5. 결과 요약
    print(f"\n{'=' * 60}")
    print(f"✅ 완료!")
    print(f"   기존 매핑 복구: {len(already_mapped)}개")
    print(f"   신규 번역: {len(all_translations)}개")
    print(f"   총 처리: {len(already_mapped) + len(all_translations)}개")


if __name__ == "__main__":
    main()
