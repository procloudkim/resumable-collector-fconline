from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set

from .keywords import KOREA_KEYWORDS, PORTUGAL_KEYWORDS, PLAYER_TO_TEAM
from .preprocess import preprocess_text


def _contains_any(text: str, terms: Set[str]) -> bool:
    t = preprocess_text(text)
    for term in terms:
        if term and term in t:
            return True
    return False


def detect_mentions_flags(text: str) -> Dict[str, int]:
    korea_terms = {t for v in KOREA_KEYWORDS.values() for t in v}
    portugal_terms = {t for v in PORTUGAL_KEYWORDS.values() for t in v}
    return {
        "mentions_korea": int(_contains_any(text, korea_terms)),
        "mentions_portugal": int(_contains_any(text, portugal_terms)),
    }


def detect_player_flags(text: str) -> Dict[str, int]:
    """Return per-player mention flags keyed by canonical player name.

    Example: {"손흥민": 1, "호날두": 0, ...}
    """
    t = preprocess_text(text)
    flags: Dict[str, int] = {}
    for player, terms in {**KOREA_KEYWORDS, **PORTUGAL_KEYWORDS}.items():
        hit = 0
        for term in terms:
            if term and term in t:
                hit = 1
                break
        flags[player] = hit
    return flags

