from __future__ import annotations

"""
이미지/로고 다운로드 모듈

WHY: 시각화 및 후처리를 위해 URL만 저장하지 않고 실제 파일을 보관해야 한다.
HOW: ThreadPool로 제한 병렬(기본 6~8) 다운로드, 재시도/백오프, 캐시 스킵, 실패 기록.
     실패 시 not_found.png를 사용(최초 실행 시 자동 생성).
"""

import base64
import concurrent.futures as cf
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

import requests

from .utils import ensure_dir


@dataclass
class DownloadTask:
    url: str
    out_path: Path


def ensure_not_found_image(path: Path) -> None:
    """
    WHY: 다운로드 실패 시 대체 이미지를 사용해 시각화 파이프라인이 끊기지 않도록 한다.
    HOW: 1x1 투명 PNG를 base64로 내장해 파일이 없으면 생성한다.
    """
    if path.exists() and path.stat().st_size > 0:
        return
    ensure_dir(path.parent)
    # 1x1 transparent PNG
    b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
        "/w8AAn8B9m1nWJkAAAAASUVORK5CYII="
    )
    path.write_bytes(base64.b64decode(b64))


def _download_one(url: str, out_path: Path, timeout: int = 10, retries: int = 3) -> Tuple[Path, bool]:
    ensure_dir(out_path.parent)
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path, True  # cache hit
    for i in range(retries):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200 and r.content:
                out_path.write_bytes(r.content)
                return out_path, True
        except Exception:
            pass
        time.sleep(2 ** i)
    return out_path, False


def download_many(tasks: Iterable[DownloadTask], max_workers: int = 8, timeout: int = 10, retries: int = 3) -> Tuple[int, int]:
    """여러 이미지를 병렬로 다운로드

    반환: (성공 개수, 실패 개수)
    """
    ok = 0
    fail = 0
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(_download_one, t.url, t.out_path, timeout, retries) for t in tasks]
        for f in cf.as_completed(futs):
            _, success = f.result()
            ok += 1 if success else 0
            fail += 0 if success else 1
    return ok, fail

