from __future__ import annotations

"""
백필(선택): 실패 이미지/로고 재다운로드

WHY: 실행 중 실패한 이미지 다운로드를 나중에 다시 시도할 수 있게 한다.
HOW: failures_YYYY-MM-DD.txt 를 읽어 다시 다운로드한다(옵션).
"""

from pathlib import Path
from typing import List

from .images import DownloadTask, download_many


def retry_failures(state_dir: Path, out_dir: Path, threads: int = 6) -> int:
    tasks: List[DownloadTask] = []
    for p in state_dir.glob("failures_*.txt"):
        for line in p.read_text(encoding="utf-8").splitlines():
            parts = [x.strip() for x in line.split(",")]
            if len(parts) < 2:
                continue
            url = parts[1]
            name = Path(url).name
            tasks.append(DownloadTask(url=url, out_path=out_dir / name))
    ok, fail = download_many(tasks, max_workers=threads)
    return ok

