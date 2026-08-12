"""Deterministic text and vector similarity helpers."""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Sequence

_STOPWORDS = {
    "ai",
    "ban",
    "cac",
    "cho",
    "co",
    "cua",
    "de",
    "duoc",
    "gi",
    "hoi",
    "la",
    "minh",
    "mot",
    "nao",
    "nay",
    "nhung",
    "the",
    "thi",
    "toi",
    "trong",
    "va",
    "ve",
    "voi",
    "dang",
    "tham",
    "gia",
    "phuong",
    "phap",
}

_GENERIC_TITLE_TERMS = _STOPWORDS | {
    "ap",
    "dung",
    "hieu",
    "hoc",
    "lam",
    "nen",
    "qua",
    "quy",
    "trinh",
    "buoc",
    "cach",
    "learning",
    "study",
    "technique",
}


def normalize_text(text: str) -> str:
    # Vietnamese đ/Đ does not decompose under NFKD, so fold it explicitly.
    decomposed = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[^\W_]+", ascii_text, flags=re.UNICODE))


def content_tokens(text: str) -> set[str]:
    return {token for token in normalize_text(text).split() if len(token) > 1 and token not in _STOPWORDS}


def query_coverage(query: str, document: str) -> float:
    query_tokens = content_tokens(query)
    if not query_tokens:
        return 0.0
    return len(query_tokens & content_tokens(document)) / len(query_tokens)


def distinctive_title_match(query: str, title: str) -> float:
    """Return 1 when a meaningful query term appears in the source title."""
    query_terms = content_tokens(query) - _GENERIC_TITLE_TERMS
    title_terms = content_tokens(title) - _GENERIC_TITLE_TERMS
    return 1.0 if query_terms & title_terms else 0.0


def phrase_score(query: str, document: str) -> float:
    query_parts = [token for token in normalize_text(query).split() if token not in _STOPWORDS]
    document_parts = [token for token in normalize_text(document).split() if token not in _STOPWORDS]
    if not query_parts or not document_parts:
        return 0.0
    longest = 0
    for query_start in range(len(query_parts)):
        for document_start in range(len(document_parts)):
            run = 0
            while (
                query_start + run < len(query_parts)
                and document_start + run < len(document_parts)
                and query_parts[query_start + run] == document_parts[document_start + run]
            ):
                run += 1
            longest = max(longest, run)
    if longest < 2:
        return 0.0
    return min(1.0, longest / 3.0)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))
