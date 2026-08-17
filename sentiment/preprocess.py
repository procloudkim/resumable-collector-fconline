from __future__ import annotations

import re
import unicodedata

LAUGH_TOKEN = "[LAUGH]"


_RE_LAUGH = re.compile(r"([ㅋㅎ])\1{1,}")  # sequences of ㅋㅋ.. or ㅎㅎ..
_RE_REPEAT = re.compile(r"(.)\1{2,}")  # 3+ repeats of any char


def _normalize_unicode(text: str) -> str:
    # Normalize to NFC for Hangul consistency
    return unicodedata.normalize("NFC", text)


def normalize_laughter(text: str) -> str:
    # Replace laughter sequences (ㅋ/ㅎ, length>=2) with a single token
    return _RE_LAUGH.sub(LAUGH_TOKEN, text)


def compress_repeats(text: str) -> str:
    # Reduce long repeats to 2, but keep 'ㄷ' sequences as-is.
    def repl(m: re.Match[str]) -> str:
        ch = m.group(1)
        if ch == "ㄷ":
            return ch * len(m.group(0))  # keep as-is
        # don't interfere with the LAUGH token contents
        if LAUGH_TOKEN in m.string[max(0, m.start()-8):m.end()+8]:
            return m.group(0)
        return ch * 2

    return _RE_REPEAT.sub(repl, text)


def to_lower(text: str) -> str:
    # Lowercase affects Latin/ASCII; Hangul unaffected
    return text.lower()


def tidy_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def preprocess_text(text: str) -> str:
    """Apply normalization pipeline.

    - NFC normalize
    - Lowercase roman text
    - Convert laughter runs to [LAUGH]
    - Compress other repeats (3+ -> 2), excluding ㄷ series and [LAUGH]
    - Tidy whitespace
    Emojis are preserved.
    """
    if not isinstance(text, str):
        return ""
    t = _normalize_unicode(text)
    t = to_lower(t)
    t = normalize_laughter(t)
    t = compress_repeats(t)
    t = tidy_spaces(t)
    return t

