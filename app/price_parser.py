from __future__ import annotations

"""
Korean money string parser

WHY: Handles formats like "1조 4,900억", "7,250조", "9,850,000,000".
HOW: Converts 조(10^12)/억(10^8) units to integers with simple rules.
"""

import re
from typing import Optional

JO = 1_000_000_000_000  # 10^12
EOK = 100_000_000  # 10^8


def _digits(s: str) -> Optional[int]:
    s2 = re.sub(r"[^0-9]", "", s)
    if not s2:
        return None
    try:
        return int(s2)
    except Exception:
        return None


def korean_money_to_int(text: Optional[str]) -> Optional[int]:
    """Convert Korean currency strings to integer.

    Rules (in order):
    1) If only digits and commas, parse directly
    2) For "X조 Y억" -> X*10^12 + Y*10^8
    3) For standalone "X조" or "Y억"
    4) Fallback: strip non-digits and parse; return None if empty
    """
    if text is None:
        return None
    s = (str(text) or "").strip()
    if not s:
        return None

    # 1) plain digits (with commas)
    if re.fullmatch(r"[0-9,]+", s):
        try:
            return int(s.replace(",", ""))
        except Exception:
            pass

    # 2) X조 Y억 combo
    total = 0
    matched = False
    m = re.search(r"(\d{1,3}(?:,\d{3})*)\s*조", s)
    if m:
        total += int(m.group(1).replace(",", "")) * JO
        matched = True
    m = re.search(r"(\d{1,3}(?:,\d{3})*)\s*억", s)
    if m:
        total += int(m.group(1).replace(",", "")) * EOK
        matched = True
    if matched:
        return total

    # 3) standalone (조 | 억)
    m = re.search(r"^(\d{1,3}(?:,\d{3})*)\s*조$", s)
    if m:
        return int(m.group(1).replace(",", "")) * JO
    m = re.search(r"^(\d{1,3}(?:,\d{3})*)\s*억$", s)
    if m:
        return int(m.group(1).replace(",", "")) * EOK

    # 4) fallback: digits only
    return _digits(s)

