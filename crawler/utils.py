"""
공통 유틸리티 함수
- 제목 매핑 (일본어 → 한국어)
- 리버스 작품 판별
- 장르 번역
"""

import json
from pathlib import Path
from typing import Optional


# 프로젝트 루트
project_root = Path(__file__).parent.parent


# 장르 번역 딕셔너리 (일본어 → 한국어)
GENRE_TRANSLATIONS = {
    # 픽코마 장르
    'ファンタジー': '판타지',
    '恋愛': '연애',
    'アクション': '액션',
    'ドラマ': '드라마',
    'ホラー': '호러',
    'ミステリー': '미스터리',
    'スポーツ': '스포츠',
    'グルメ': '요리',
    '日常': '일상',
    'TL': 'TL',
    'BL': 'BL',
    '裏社会': '뒷세계',
    'アングラ': '언더그라운드',
    'ホラー・ミステリー': '호러/미스터리',
    '裏社会・アングラ': '뒷세계/언더그라운드',

    # 일반 장르
    'コメディ': '코미디',
    'サスペンス': '서스펜스',
    'SF': 'SF',
    'ヒューマンドラマ': '휴먼드라마',
    '学園': '학원',
    '恋愛ドラマ': '연애드라마',
    'ハートフル': '훈훈',
    '復讐': '복수',
    '異世界': '이세계',
    '転生': '전생',
    '冒険': '모험',
    'バトル': '배틀',
    '格闘': '격투',
    '歴史': '역사',
    '時代劇': '시대극',
    '推理': '추리',
    '探偵': '탐정',
    'サバイバル': '서바이벌',
    'ゾンビ': '좀비',
    '医療': '의료',
    '料理': '요리',
    '音楽': '음악',
    '芸能': '연예',
    'ビジネス': '비즈니스',
    'お仕事': '직업',
    '家族': '가족',
    '友情': '우정',
    '青春': '청춘',
    '成長': '성장',
    '職業': '직업',
    '日常系': '일상계',
    '癒し': '힐링',
    '感動': '감동',
    '泣ける': '눈물',
    'ギャグ': '개그',
    'ラブコメ': '러브코미디',
}


# 참조 데이터 로드 (지연 로딩)
_riverse_titles = None
_title_mappings = None


def load_riverse_titles() -> dict:
    """리버스 작품 목록 로드 (캐싱)"""
    global _riverse_titles

    if _riverse_titles is None:
        try:
            path = project_root / 'data' / 'riverse_titles.json'
            with open(path, 'r', encoding='utf-8') as f:
                _riverse_titles = json.load(f)
            print(f"✅ 리버스 작품 {len(_riverse_titles)}개 로드")
        except FileNotFoundError:
            print(f"⚠️  riverse_titles.json 파일이 없습니다. 빈 딕셔너리 사용")
            _riverse_titles = {}
        except json.JSONDecodeError:
            print(f"❌ riverse_titles.json 파싱 실패. 빈 딕셔너리 사용")
            _riverse_titles = {}

    return _riverse_titles


def load_title_mappings() -> dict:
    """한국어 제목 매핑 로드 (캐싱)"""
    global _title_mappings

    if _title_mappings is None:
        try:
            path = project_root / 'data' / 'title_mappings.json'
            with open(path, 'r', encoding='utf-8') as f:
                _title_mappings = json.load(f)
            print(f"✅ 한국어 제목 {len(_title_mappings)}개 로드")
        except FileNotFoundError:
            print(f"⚠️  title_mappings.json 파일이 없습니다. 빈 딕셔너리 사용")
            _title_mappings = {}
        except json.JSONDecodeError:
            print(f"❌ title_mappings.json 파싱 실패. 빈 딕셔너리 사용")
            _title_mappings = {}

    return _title_mappings


def get_korean_title(jp_title: str) -> str:
    """
    제목 → 한국어 제목 매핑 (일본어 + 영어 지원)

    Args:
        jp_title: 일본어 또는 영어 제목

    Returns:
        한국어 제목 (없으면 빈 문자열)
    """
    if not jp_title:
        return ""

    riverse = load_riverse_titles()
    mappings = load_title_mappings()

    # 1순위: 정확한 매칭 (리버스 작품)
    if jp_title in riverse:
        return riverse[jp_title]

    # 2순위: 정확한 매칭 (일반 매핑)
    if jp_title in mappings:
        return mappings[jp_title]

    # 3순위: 대소문자 무시 매칭 (영어 제목용)
    title_lower = jp_title.lower()
    for key, kr in riverse.items():
        if key.lower() == title_lower:
            return kr
    for key, kr in mappings.items():
        if key.lower() == title_lower:
            return kr

    # 4순위: 대괄호 제거 후 매칭 (【】, [], ())
    cleaned = jp_title
    for bracket in ['【', '】', '[', ']', '(', ')']:
        cleaned = cleaned.replace(bracket, '')

    if cleaned != jp_title:
        if cleaned in riverse:
            return riverse[cleaned]
        if cleaned in mappings:
            return mappings[cleaned]

    # 5순위: 부분 매칭 (4글자 이상)
    if len(jp_title) >= 4:
        for jp, kr in riverse.items():
            if len(jp) >= 4 and jp in jp_title:
                return kr

        for jp, kr in mappings.items():
            if len(jp) >= 4 and jp in jp_title:
                return kr

    return ""


def is_riverse_title(jp_title: str) -> bool:
    """
    리버스 작품 여부 판별

    Args:
        jp_title: 일본어 제목

    Returns:
        True: 리버스 작품, False: 일반 작품
    """
    if not jp_title:
        return False

    riverse = load_riverse_titles()

    # 정확한 매칭
    if jp_title in riverse:
        return True

    # 대괄호 제거 후 매칭
    cleaned = jp_title
    for bracket in ['【', '】', '[', ']', '(', ')']:
        cleaned = cleaned.replace(bracket, '')

    if cleaned in riverse:
        return True

    # 부분 매칭 (4글자 이상)
    if len(jp_title) >= 4:
        for jp in riverse.keys():
            if len(jp) >= 4 and jp in jp_title:
                return True

    return False


def translate_genre(jp_genre: str) -> str:
    """
    일본어 장르 → 한국어 번역

    Args:
        jp_genre: 일본어 장르 (예: "ファンタジー" 또는 "ファンタジー / アクション")

    Returns:
        한국어 장르 (없으면 원문 그대로)
    """
    if not jp_genre:
        return ""

    # 복합 장르 처리 (예: "ファンタジー / アクション")
    if ' / ' in jp_genre or '/' in jp_genre:
        # "/" 또는 " / "로 분리
        separator = ' / ' if ' / ' in jp_genre else '/'
        genres = jp_genre.split(separator)
        translated = []

        for genre in genres:
            genre = genre.strip()
            if genre in GENRE_TRANSLATIONS:
                translated.append(GENRE_TRANSLATIONS[genre])
            else:
                # 부분 매칭 시도
                found = False
                for jp, kr in GENRE_TRANSLATIONS.items():
                    if jp in genre:
                        translated.append(kr)
                        found = True
                        break
                if not found:
                    translated.append(genre)  # 원문 유지

        return ' / '.join(translated)

    # 단일 장르
    jp_genre = jp_genre.strip()

    # 정확한 매칭
    if jp_genre in GENRE_TRANSLATIONS:
        return GENRE_TRANSLATIONS[jp_genre]

    # 부분 매칭
    for jp, kr in GENRE_TRANSLATIONS.items():
        if jp in jp_genre:
            return kr

    # 매칭 실패 - 원문 그대로
    return jp_genre


if __name__ == "__main__":
    # 테스트
    print("=" * 60)
    print("유틸리티 함수 테스트")
    print("=" * 60)

    # 장르 번역 테스트
    print("\n[장르 번역 테스트]")
    test_genres = [
        'ファンタジー',
        '恋愛',
        'ファンタジー / アクション',
        'ホラー・ミステリー',
        '알 수 없는 장르'
    ]
    for genre in test_genres:
        print(f"  {genre} → {translate_genre(genre)}")

    # 리버스 판별 테스트
    print("\n[리버스 작품 판별 테스트]")
    riverse = load_riverse_titles()
    if riverse:
        sample_titles = list(riverse.keys())[:3]
        for title in sample_titles:
            kr = get_korean_title(title)
            is_rv = is_riverse_title(title)
            print(f"  {title}")
            print(f"    → 한국어: {kr}")
            print(f"    → 리버스: {is_rv}")
    else:
        print("  ⚠️  리버스 작품 데이터 없음")

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)
