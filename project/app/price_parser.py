from __future__ import annotations

"""
가격(한글 단위 포함) 파서

WHY: 가격이 "1조 4,900억", "7,250조", "9,850,000,000" 등 다양한 표기로 제공된다.
HOW: 조(10^12)/억(10^8) 단위를 안전하게 정수로 변환하는 순수 함수를 제공하고,
     단위 테스트로 검증한다.
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
    """한글 혼합 표기의 금액을 정수로 변환

    규칙(우선순위):
    1) alt/title 등 순수 숫자(콤마 포함) → 정수
    2) "X조 Y억" → X*10^12 + Y*10^8
    3) "X조" 또는 "Y억" 단독 → 해당 단위 변환
    4) 기타 → 숫자만 추출하여 정수(최후 수단)
    실패 시 None
    """
    if text is None:
        return None
    s = (str(text) or "").strip()
    if not s:
        return None

    # 1) 순수 숫자(콤마 포함)
    if re.fullmatch(r"[0-9,]+", s):
        try:
            return int(s.replace(",", ""))
        except Exception:
            pass

    # 2) X조 Y억 조합
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

    # 3) 단독 단위(조 | 억)
    m = re.search(r"^(\d{1,3}(?:,\d{3})*)\s*조$", s)
    if m:
        return int(m.group(1).replace(",", "")) * JO
    m = re.search(r"^(\d{1,3}(?:,\d{3})*)\s*억$", s)
    if m:
        return int(m.group(1).replace(",", "")) * EOK

    # 4) 최후 수단: 숫자만 추출
    return _digits(s)

