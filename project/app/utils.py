from __future__ import annotations

"""
공통 유틸리티

WHY: 여러 모듈에서 공통으로 쓰는 경로/슬립/원자적 쓰기 기능을 한 곳에 모아 재사용성을 높인다.
HOW: 랜덤 슬립, 디렉터리 생성, 임시 파일에 쓰고 rename하는 atomic_write를 제공한다.
"""

import os
import random
import tempfile
import time
from pathlib import Path


def polite_sleep(min_s: float = 0.3, max_s: float = 1.0) -> None:
    """예의 있는 랜덤 슬립

    WHY: 서버 차단(429) 및 CAPTCHA 위험을 줄이기 위해 요청 간 지연을 둔다.
    HOW: [min_s, max_s] 범위에서 균등분포로 시간을 골라 sleep한다.
    """
    if max_s <= 0:
        return
    delay = random.uniform(min_s, max_s)
    time.sleep(delay)


def ensure_dir(p: Path) -> None:
    """디렉터리 생성(존재해도 OK)."""
    p.mkdir(parents=True, exist_ok=True)


def atomic_write(path: Path, data: bytes) -> None:
    """원자적 쓰기(Windows 대응)

    WHY: CSV를 부분적으로 쓰다 중단되면 파일이 손상될 수 있다. 임시 파일에 모두 쓴 뒤 rename한다.
    HOW: 같은 디렉터리에 임시 파일을 만든 후 os.replace로 교체(Windows에서도 원자적 동작).
    """
    ensure_dir(path.parent)
    with tempfile.NamedTemporaryFile(dir=str(path.parent), delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)

