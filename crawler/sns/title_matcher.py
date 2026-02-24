"""
일본어 타이틀 퍼지 매칭
전략: 정규화 → 완전일치 → 부분일치 → Levenshtein
"""
import re
import unicodedata
from typing import Optional, Tuple


def normalize_title(title: str) -> str:
    """일본어 타이틀 정규화."""
    if not title:
        return ""
    t = title.strip()
    # 끝에 붙은 괄호 제거 (【最新話】, [完結], (フルカラー) 등)
    t = re.sub(r'[\[【（(][^\]】）)]*[\]】）)]$', '', t).strip()
    # 공백 정규화
    t = re.sub(r'[\s　]+', ' ', t).strip()
    # 유니코드 정규화 (NFKC)
    t = unicodedata.normalize('NFKC', t)
    return t


def title_similarity(a: str, b: str) -> float:
    """두 타이틀 간 유사도 (0.0~1.0)."""
    na = normalize_title(a).lower()
    nb = normalize_title(b).lower()

    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    # 부분 일치
    if na in nb or nb in na:
        return 0.9
    # Levenshtein 기반
    return _levenshtein_ratio(na, nb)


def _levenshtein_ratio(s1: str, s2: str) -> float:
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    distances = range(len(s1) + 1)
    for c2 in s2:
        new_distances = [distances[0] + 1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                new_distances.append(distances[i1])
            else:
                new_distances.append(1 + min(distances[i1], distances[i1 + 1], new_distances[-1]))
        distances = new_distances
    max_len = max(len(s1), len(s2))
    return 1.0 - (distances[-1] / max_len) if max_len > 0 else 0.0


def best_match(query: str, candidates: list, threshold: float = 0.75) -> Optional[Tuple[dict, float]]:
    """후보 목록에서 최적 매칭 찾기.

    Args:
        query: 우리 DB의 일본어 타이틀
        candidates: dict 리스트 (title, title_japanese, native 등의 키)
        threshold: 최소 유사도
    Returns:
        (best_candidate, score) 또는 None
    """
    best = None
    best_score = 0.0

    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        for key in ['title', 'title_japanese', 'native', 'romaji', 'english',
                     'title_romaji', 'title_english']:
            val = cand.get(key, '')
            if not val or not isinstance(val, str):
                continue
            score = title_similarity(query, val)
            if score > best_score:
                best_score = score
                best = cand

    if best and best_score >= threshold:
        return (best, best_score)
    return None
