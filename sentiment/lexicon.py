from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .preprocess import LAUGH_TOKEN, preprocess_text


# Seed slang lexicon (expand later or load from file)
SEED_POS = {
    "최고",
    "끝내준다",
    "쩐다",
    "개쩐다",
    "굿",
    "짱",
    "레전드",
    "대박",
    "꿀잼",
    "개꿀",
    "잘했다",
    "멋지다",
    "훌륭",
}

SEED_NEG = {
    "별로",
    "최악",
    "쓰레기",
    "못했다",
    "형편없다",
    "개노잼",
    "노잼",
    "실망",
    "혐",
    "역겹",
}


def _load_external(path: str) -> Tuple[Set[str], Set[str]]:
    pos, neg = set(), set()
    if not os.path.isfile(path):
        return pos, neg
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            token, label = parts[0].strip(), parts[1].strip().lower()
            if label in ("pos", "positive", "+"):
                pos.add(token)
            elif label in ("neg", "negative", "-"):
                neg.add(token)
    return pos, neg


@dataclass
class LexiconScorer:
    pos_terms: Set[str]
    neg_terms: Set[str]
    alpha: float = 1.0  # sigmoid sharpness
    laugh_bonus: float = 0.5  # bonus to raw for [LAUGH] presence

    @classmethod
    def with_seed_and_file(cls, path: Optional[str] = None) -> "LexiconScorer":
        pos = set(SEED_POS)
        neg = set(SEED_NEG)
        if path:
            p2, n2 = _load_external(path)
            pos.update(p2)
            neg.update(n2)
        return cls(pos_terms=pos, neg_terms=neg)

    def _hits(self, text: str) -> Tuple[int, int, bool]:
        p = n = 0
        t = preprocess_text(text)
        laugh = LAUGH_TOKEN in t
        # simple substring hits (space-delimited robustness is limited; acceptable for seed)
        for term in self.pos_terms:
            if term and term in t:
                p += 1
        for term in self.neg_terms:
            if term and term in t:
                n += 1
        return p, n, laugh

    def score(self, text: str) -> Tuple[float, str, Dict[str, int]]:
        p, n, laugh = self._hits(text)
        raw = (p - n) + (self.laugh_bonus if laugh else 0.0)
        prob = 1.0 / (1.0 + math.exp(-self.alpha * raw))
        if prob > 0.6:
            label = "positive"
        elif prob < 0.4:
            label = "negative"
        else:
            label = "neutral"
        return prob, label, {"pos_hits": p, "neg_hits": n, "laugh": int(laugh)}

